"""Deterministic source and documentation inspection."""
import ast
import re
from pathlib import Path
from .phrases import STEM_PHRASES, NOSTEM_PHRASES, GENERIC_NAMES

EXCLUDED = {'.git', '__pycache__', '.venv', 'venv', 'env', '.env', 'virtualenv'}


def match_claims(text):
    text = re.sub(r'^\s*```[^\n]*\n.*?^\s*```[^\n]*(?:\n|$)', '', text, flags=re.M | re.S)
    text = text.replace('`', '').lower()
    def consume(phrases, value):
        found = []
        for phrase in sorted(phrases, key=len, reverse=True):
            while phrase in value:
                index = value.index(phrase)
                found.append(phrase)
                value = value[:index] + ' ' * len(phrase) + value[index + len(phrase):]
        return found, value
    denied, text = consume(NOSTEM_PHRASES, text)
    positive, _ = consume(STEM_PHRASES, text)
    return positive, denied


def evidence(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    aliases = {}
    from_imports = set()
    shadow = {node.name for node in ast.walk(tree)
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split('.')[0]] = item.name if item.asname else item.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            for item in node.names:
                aliases[item.asname or item.name] = (node.module or '') + '.' + item.name
                from_imports.add(item.asname or item.name)
    def resolve(node):
        if isinstance(node, ast.Name):
            return '' if node.id in shadow else aliases.get(node.id, '')
        if isinstance(node, ast.Attribute):
            base = resolve(node.value)
            return base + '.' + node.attr if base and node.attr not in shadow else ''
        return ''
    classes = {'PorterStemmer', 'LancasterStemmer', 'SnowballStemmer', 'RegexpStemmer', 'RSLPStemmer', 'ISRIStemmer', 'Cistem'}
    def constructor(node):
        if not isinstance(node, ast.Call):
            return None
        name = resolve(node.func)
        if name.startswith('nltk.stem.') and name.rsplit('.', 1)[-1] in classes:
            return 'nltk'
        if name == 'gensim.parsing.porter.PorterStemmer':
            return 'nltk'
        if name == 'Stemmer.Stemmer':
            return 'py'
        return None
    assigned = {}
    blocked = set()
    assignments = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))]
    for _ in range(len(assignments) + 1):
        for node in assignments:
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            kind = constructor(value)
            if isinstance(value, ast.Name):
                kind = assigned.get(value.id)
            for target in targets:
                if isinstance(target, ast.Name):
                    if kind:
                        assigned[target.id] = kind
                    if isinstance(value, ast.Call):
                        func = value.func
                        if (isinstance(func, ast.Name) and func.id in shadow) or (isinstance(func, ast.Attribute) and (func.attr in shadow or isinstance(func.value, ast.Name) and func.value.id in shadow)):
                            blocked.add(target.id)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            base = func.value
            if func.attr in shadow or (isinstance(base, ast.Name) and (base.id in blocked or base.id in shadow)):
                continue
            if isinstance(base, ast.Call):
                if isinstance(base.func, ast.Name) and base.func.id in shadow:
                    continue
                if isinstance(base.func, ast.Attribute) and (base.func.attr in shadow or isinstance(base.func.value, ast.Name) and base.func.value.id in shadow):
                    continue
            kind = constructor(base) or (assigned.get(base.id) if isinstance(base, ast.Name) else None)
            if kind == 'nltk' and func.attr in {'stem', 'stem_sentence'}:
                return True
            if kind == 'py' and func.attr in {'stemWord', 'stemWords'}:
                return True
            if func.attr in GENERIC_NAMES:
                return True
        elif isinstance(func, ast.Name) and func.id not in shadow and func.id in from_imports:
            resolved = resolve(func)
            if resolved and resolved.rsplit('.', 1)[-1] in GENERIC_NAMES:
                return True
    return False


def audit(repo, ignore=(), decisions=None):
    root = Path(repo)
    if not root.is_dir():
        raise OSError('Repository is not a directory: ' + str(root))
    docs, fixtures, sources = [], [], []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        name = relative.as_posix()
        skip = any(part in EXCLUDED for part in relative.parts) or any(name.startswith(prefix) for prefix in ignore)
        # Also detect custom-named Python virtual environments.
        skip = skip or any((parent / 'pyvenv.cfg').is_file() for parent in path.parents if parent != root and root in parent.parents)
        if skip or not path.is_file():
            if decisions is not None and path.is_file(): decisions.append('SKIP ' + name)
            continue
        is_doc = name == 'README.md' or (relative.parts[0] == 'docs' and path.suffix == '.md')
        is_fixture = 'tests' in relative.parts[:-1]
        if path.suffix == '.py' or is_doc or is_fixture:
            text = path.read_text(encoding='utf-8')
            if decisions is not None: decisions.append('SCAN ' + name)
            if path.suffix == '.py': sources.append(text)
            if is_doc: docs.append((name, text))
            elif is_fixture: fixtures.append((name, text))
    has_evidence = any(evidence(source) for source in sources)
    findings = []
    doc_positive = any(match_claims(text)[0] for _, text in docs)
    for name, text in docs + fixtures:
        positive, denied = match_claims(text)
        test_only = (name, text) in fixtures
        if positive and not has_evidence and not (test_only and doc_positive):
            for phrase in positive:
                findings.append(dict(verdict='documented-stemming-claim-false', severity='MEDIUM' if test_only else 'HIGH', path=name, message='Unsupported claim: ' + phrase))
        if denied and has_evidence and not test_only:
            for phrase in denied:
                findings.append(dict(verdict='documented-no-stemming-claim-false', severity='HIGH', path=name, message='Code contradicts denial: ' + phrase))
    return findings
