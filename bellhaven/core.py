import contextlib
import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://analyst-assessment-production.up.railway.app'

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def load_env():
    for path in (ROOT.parents[1] / '.env', ROOT / '.env'):
        if path.exists():
            for line in path.read_text().splitlines():
                if '=' in line and not line.lstrip().startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('\"\''))

def request(url, method='GET', payload=None, token=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'BellhavenReconciliation/1.0'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers['Content-Type'] = 'application/json'
    # GETs are safe to retry. Writes are never blindly retried.
    for attempt in range(3 if method == 'GET' else 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data, headers, method=method), timeout=30) as response:
                raw = response.read().decode()
                return json.loads(raw) if 'json' in response.headers.get('Content-Type', '') else raw
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:1000]
            if method == 'GET' and exc.code in (429, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f'{method} {urllib.parse.urlparse(url).path}: HTTP {exc.code}: {body}') from None
        except (urllib.error.URLError, TimeoutError):
            if method == 'GET' and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise

class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []
    def find(self, tag):
        return [n for n in self.walk() if n.tag == tag]
    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()
    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)

class Tree(HTMLParser):
    VOID = {'br', 'img', 'meta', 'link', 'input', 'hr', 'source', 'wbr'}
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag == 'br':
            node.children.append('\n')
        if tag not in self.VOID:
            self.stack.append(node)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break
    def handle_data(self, data):
        self.stack[-1].children.append(data)

def parse_location(html, url):
    tree = Tree(html).root
    headings = tree.find('h1')
    fields = {}
    for dl in tree.find('dl'):
        current = None
        for child in dl.children:
            if not isinstance(child, Node):
                continue
            if child.tag == 'dt':
                current = child.text().strip().lower()
            elif child.tag == 'dd' and current:
                fields[current] = child
    if not headings or 'address' not in fields or 'care offerings' not in fields:
        raise ValueError(f'Incomplete location detail at {url}')
    address = fields['address'].text().strip()
    match = re.fullmatch(r'(.+?)\s*\n\s*(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', address)
    if not match:
        raise ValueError(f'Unrecognized address at {url}: {address}')
    badges = [n.text().strip() for n in fields['care offerings'].walk() if 'badge' in n.attrs.get('class', '').split()]
    return dict(name=headings[0].text().strip(), street=match[1].strip(), city=match[2].strip(), state=match[3], zip=match[4], care_offerings=badges or [fields['care offerings'].text().strip()], source_url=url)

def scrape(base=BASE, data_dir=None):
    queue = [base + '/', base + '/communities', base + '/about']
    seen, locations, directory_urls = set(), {}, set()
    declared = set()
    snapshot = Path(data_dir or ROOT / 'data') / 'website' / now().replace(':', '-')
    snapshot.mkdir(parents=True, exist_ok=True)
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        if len(seen) > 300:
            raise ValueError('Crawl exceeded safety limit')
        html = request(url)
        seen.add(url)
        (snapshot / (digest(url) + '.html')).write_text(html)
        tree = Tree(html).root
        path = urllib.parse.urlparse(url).path
        if path.startswith('/communities/'):
            locations[url] = parse_location(html, url)
        else:
            declared.update(int(n) for n in re.findall(r'(\d+) communities listed', tree.text()))
        for link in tree.find('a'):
            href = urllib.parse.urljoin(url, link.attrs.get('href', ''))
            parsed = urllib.parse.urlparse(href)
            if parsed.netloc != urllib.parse.urlparse(base).netloc:
                continue
            if parsed.path == '/communities' or parsed.path.startswith('/communities/'):
                canonical = urllib.parse.urlunparse(parsed._replace(fragment=''))
                if path == '/communities' and parsed.path.startswith('/communities/'):
                    directory_urls.add(canonical)
                if canonical not in seen and canonical not in queue:
                    queue.append(canonical)
    if len(declared) != 1 or len(directory_urls) != next(iter(declared), -1):
        raise ValueError(f'Incomplete directory crawl: declared={declared}, discovered={len(directory_urls)}')
    if not locations or any(url not in locations for url in directory_urls):
        raise ValueError('Missing community detail pages; aborting reconciliation')
    result = {'fetched_at': now(), 'pages': sorted(seen), 'directory_count': len(directory_urls), 'locations': sorted(locations.values(), key=lambda x: x['name']), 'snapshot_dir': str(snapshot)}
    (ROOT / 'data' / 'locations.json').write_text(json.dumps(result, indent=2))
    return result

class CRM:
    def __init__(self, base=None, token=None):
        load_env()
        self.base = (base or os.environ.get('CRM_BASE_URL', BASE)).rstrip('/')
        self.token = token or os.environ.get('CRM_TOKEN')
        if not self.token:
            raise ValueError('Set CRM_TOKEN in .env or the environment before accessing the CRM')
    def call(self, path, method='GET', payload=None):
        return request(self.base + '/api/v1/' + path, method, payload, self.token)
    def get(self, account_id):
        value = self.call('accounts/' + urllib.parse.quote(str(account_id), safe=''))
        if isinstance(value, dict) and isinstance(value.get('account'), dict):
            return value['account']
        return value
    def list_accounts(self):
        records, seen = [], set()
        for page in range(1, 1001):
            response = self.call('accounts?' + urllib.parse.urlencode({'page': page, 'page_size': 100}))
            if isinstance(response, list):
                items, total = response, None
            elif isinstance(response, dict):
                items = next((response[k] for k in ('items', 'accounts', 'data', 'results') if isinstance(response.get(k), list)), None)
                total = response.get('total', response.get('total_count'))
            else:
                raise ValueError('Unknown account list format')
            if items is None:
                raise ValueError('Account list does not contain a recognized record array')
            if not items:
                return records
            ids = {str(a['id']) for a in items}
            if ids & seen:
                raise ValueError('CRM pagination repeated records; refusing incomplete snapshot')
            records.extend(items)
            seen.update(ids)
            if total is not None and len(records) >= int(total):
                return records
        raise ValueError('CRM pagination exceeded safety limit')

def database(path=None):
    path = path or ROOT / 'data' / 'review.sqlite3'
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript('''
      PRAGMA journal_mode=WAL;
      CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, at TEXT, snapshot TEXT, parent_id TEXT);
      CREATE TABLE IF NOT EXISTS proposals(id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE, run_id INTEGER,
        title TEXT, kind TEXT, plan TEXT, evidence TEXT, state TEXT DEFAULT 'pending', reviewer TEXT,
        decided_at TEXT, result TEXT, error TEXT);
      CREATE TABLE IF NOT EXISTS operations(proposal_id INTEGER, step INTEGER, state TEXT, result TEXT,
        PRIMARY KEY(proposal_id, step));
      CREATE TABLE IF NOT EXISTS matches(run_id INTEGER, location TEXT, account_id TEXT, classification TEXT, evidence TEXT);
    ''')
    conn.commit()
    return conn

@contextlib.contextmanager
def process_lock(path=None):
    import fcntl
    with open(path or ROOT / 'data' / 'pipeline.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another reconciliation or approval is running') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)

def normalize(value):
    return ' '.join(re.findall(r'[a-z0-9]+', str(value or '').lower()))

def street_key(value):
    words = normalize(value).split()
    aliases = {'street':'st', 'road':'rd', 'avenue':'ave', 'drive':'dr', 'lane':'ln', 'boulevard':'blvd', 'court':'ct', 'place':'pl', 'north':'n', 'south':'s', 'east':'e', 'west':'w'}
    return ' '.join(aliases.get(w, w) for w in words)

def location_fields(account):
    address = account.get('address')
    if isinstance(address, dict):
        return {'street': address.get('street', address.get('line1', '')), 'city':address.get('city', ''), 'state':address.get('state', ''), 'zip':address.get('zip', address.get('postal_code', ''))}
    return {'street':account.get('street', account.get('address', account.get('address_line1', ''))), 'city':account.get('city', ''), 'state':account.get('state', ''), 'zip':account.get('zip', account.get('postal_code', ''))}

def billing_values(account):
    from decimal import Decimal, InvalidOperation
    result = []
    for key in ('lifetime_revenue', 'outstanding_ar'):
        if key not in account or account[key] is None:
            raise ValueError(f'Missing billing value {key}; parent change must wait')
        try:
            value = Decimal(str(account[key]).replace(',', '').replace('$', ''))
        except InvalidOperation:
            raise ValueError(f'Invalid billing value {key}') from None
        if not value.is_finite() or value < 0:
            raise ValueError(f'Invalid billing value {key}')
        result.append(value)
    return result

def requires_chow(account):
    revenue, ar = billing_values(account)
    return revenue > 0 and ar > 0
