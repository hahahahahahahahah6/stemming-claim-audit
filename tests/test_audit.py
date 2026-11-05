import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from stemming_claim_audit.audit import evidence, match_claims, audit
from stemming_claim_audit.phrases import STEM_PHRASES, NOSTEM_PHRASES, GENERIC_NAMES
from stemming_claim_audit.__main__ import main

EXPECTED_STEM = ['stemming', 'stemmer', 'stems', 'stem', 'stems text', 'stem text', 'stems words', 'stem words', 'stems tokens', 'stem tokens', 'word stemming', 'stemming support', 'stemmer support', 'supports stemming', 'provides stemming', 'performs stemming', 'stemming feature', 'stemming capability', 'stemming system', 'stemming model', 'supports a stemmer', 'provides a stemmer', 'stems input', 'stem input', 'stems the text', 'stem the text', 'stems the input', 'stem the input', 'reduces words to stems', 'reduce words to stems', 'reduces tokens to stems', 'reduce tokens to stems', 'converts words to stems', 'convert words to stems', 'converts tokens to stems', 'convert tokens to stems', 'text stemming', 'text stemmer', 'stemming pipeline', 'stemming step', 'stemming process', 'stems documents', 'stem documents', 'document stemming', 'word stem', 'word stems', 'porter stemmer', 'porter stemming', 'snowball stemmer', 'snowball stemming']
EXPECTED_NOSTEM = ['does not stem', 'do not stem', "doesn't stem", "don't stem", 'no stemming', 'without stemming', 'never stems', 'does not perform stemming', 'never performs stemming', 'stemming not supported', 'stemming unsupported', 'no stemming support', 'lacks stemming', 'missing stemming', 'stemming disabled', 'no stemmer', 'without a stemmer', 'does not provide stemming', 'does not support stemming', 'no word stemming', 'without stemming support', 'does not stem text', 'stemming not available', 'no text stemming']
EXPECTED_GENERIC = ['stem', 'stem_text', 'stem_word', 'stem_words', 'stem_sentence', 'stem_sentences', 'stem_document', 'stem_documents', 'stem_input', 'stem_token', 'stem_tokens', 'stem_corpus', 'stem_paragraph', 'stem_line', 'stem_lines', 'get_stem', 'get_stems', 'to_stem', 'word_stem', 'sentence_stem', 'text_stem', 'reduce_to_stem', 'stem_word_list', 'apply_stemmer']

class AuditTests(unittest.TestCase):
    def test_phrase_oracle(self):
        self.assertEqual(STEM_PHRASES, EXPECTED_STEM)
        self.assertEqual(NOSTEM_PHRASES, EXPECTED_NOSTEM)

    def test_generic_oracle(self):
        self.assertEqual(GENERIC_NAMES, EXPECTED_GENERIC)

    def test_positive_routes(self):
        for cls in ['PorterStemmer', 'SnowballStemmer', 'LancasterStemmer', 'RegexpStemmer', 'RSLPStemmer', 'ISRIStemmer', 'Cistem']:
            for code in [f'from nltk.stem import {cls} as S\ns=S()\ns.stem("x")', f'import nltk.stem as st\nst.{cls}().stem("x")']:
                with self.subTest(code=code): self.assertTrue(evidence(code))
        for code in ['from gensim.parsing.porter import PorterStemmer\np=PorterStemmer()\np.stem_sentence("x")', 'import Stemmer\ns=Stemmer.Stemmer("en")\ns.stemWord("x")', 'from Stemmer import Stemmer as S\nS("en").stemWords([])', 'import nltk\ns=nltk.stem.PorterStemmer()\ns.stem("x")']:
            with self.subTest(code=code): self.assertTrue(evidence(code))
        for name in EXPECTED_GENERIC:
            for code in [f'x.{name}("x")', f'from lib import {name} as fn\nfn("x")']:
                with self.subTest(code=code): self.assertTrue(evidence(code))

    def test_rejections(self):
        cases = [
            'import nltk.stem', 'from lib import stem', 'import stem\nstem("x")',
            'import nltk.stem as st\nclass PorterStemmer: pass\nst.PorterStemmer().stem("x")',
            'from nltk.stem import WordNetLemmatizer\nx=WordNetLemmatizer()\nx.lemmatize("x")',
            'x.lemma_; x.lemma', 'word_tokenize("x"); x.tokenize("x"); Tokenizer()',
            'pos_tag([]); x.pos_; x.tag_',
            'ne_chunk([]); x.ents; pipeline("ner"); n=NERTagger(); n.predict([])',
            'x.dep_; x.head; p=DependencyParser(); p("x")',
            'p=ConstituencyParser(); p.parse("x"); Tree.fromstring("x")',
            'stopwords.words("en"); remove_stopwords("x")',
            'from nltk.stem import PorterStemmer\np=PorterStemmer()',
            'import Stemmer\ns=Stemmer.Stemmer("en")',
            'import spacy\nspacy.load("en")',
            '\"\"\"stemming\"\"\"\n# stem\nx="stem"', 'stem',
            'import subprocess\nsubprocess.run(["stemmer"])',
            'from lib import stem\ndef stem(x): return x\nstem("x")',
            'from nltk.stem import PorterStemmer\nclass PorterStemmer: pass\np=PorterStemmer()\np.stem("x")',
            'import Stemmer\nclass Stemmer: pass\ns=Stemmer.Stemmer()\ns.stemWord("x")',
            'def stem(x): return x\nx.stem("x")',
            'from nltk.stem import PorterStemmer\nx=Other()\nx.stemWord("x")',
        ]
        for code in cases:
            with self.subTest(code=code): self.assertFalse(evidence(code))

    def test_matching(self):
        self.assertEqual(match_claims('does not stem'), ([], ['does not stem']))
        self.assertEqual(match_claims('stemming system'), (['stemming system'], []))
        self.assertEqual(match_claims('system'), (['stem'], []))
        self.assertEqual(match_claims('```py\nstemming\n```'), ([], []))
        self.assertEqual(match_claims('`stemming`'), (['stemming'], []))
        self.assertEqual(match_claims('STEMMING'), (['stemming'], []))
        self.assertEqual(match_claims('stem-text'), (['stem'], []))

    def run_cli(self, root, *args):
        out=io.StringIO()
        with contextlib.redirect_stdout(out): status=main(['audit', str(root), *args])
        return status, out.getvalue()

    def test_cli_fixtures(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            readme=root/'README.md'
            readme.write_text('stemming')
            status, out=self.run_cli(root, '--json')
            self.assertEqual(status, 2)
            finding=json.loads(out)[0]
            self.assertEqual(finding['verdict'], 'documented-stemming-claim-false')
            self.assertEqual(finding['severity'], 'HIGH')
            self.assertTrue(finding['message'])
            (root/'code.py').write_text('x.stem("x")')
            self.assertEqual(self.run_cli(root)[0], 0)
            readme.write_text('no stemming')
            status,out=self.run_cli(root)
            self.assertEqual(status, 2)
            self.assertIn('documented-no-stemming-claim-false', out)
            readme.write_text('Plain documentation')
            self.assertEqual(self.run_cli(root)[0], 0)
            (root/'code.py').unlink()
            (root/'tests').mkdir()
            (root/'tests/fixture.py').write_text('claim="stemming"')
            status,out=self.run_cli(root)
            self.assertEqual(status, 0)
            self.assertIn('MEDIUM',out)
            self.assertEqual(self.run_cli(root,'--fail-on','medium')[0],2)
            self.assertEqual(self.run_cli(root,'--ignore','tests')[1].strip(),'PASS')

    def test_split_modules(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'README.md').write_text('stemming')
            (root/'a.py').write_text('from nltk.stem import PorterStemmer\np=PorterStemmer()')
            (root/'b.py').write_text('from a import p\np.stemWord("x")')
            self.assertEqual(len(audit(root)),1)

    def test_version(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out): self.assertEqual(main(['--version']),0)
        self.assertEqual(out.getvalue().strip(),'0.1.0')

    def test_readme(self):
        root=Path(__file__).resolve().parents[1]
        self.assertEqual(match_claims((root/'README.md').read_text()),([],[]))
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)
            (target/"README.md").write_text((root/"README.md").read_text())
            self.assertEqual(audit(target),[])

    def test_scope_and_ignore(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for directory in ['docs/nested', '.git', '.venv', 'customenv']:
                (root/directory).mkdir(parents=True)
            (root/'customenv/pyvenv.cfg').write_text('home = /tmp')
            (root/'README.md').write_text('system')
            for directory in ['.git', '.venv', 'customenv']:
                (root/directory/'evidence.py').write_text('x.stem("x")')
            self.assertEqual(audit(root)[0]['severity'], 'HIGH')
            (root/'docs/nested/claim.md').write_text('stemming')
            self.assertEqual(len(audit(root)), 2)
            self.assertEqual(audit(root, ['README', 'docs/']), [])
            (root/'real.py').write_text('x.stem("x")')
            self.assertEqual(audit(root), [])
            self.assertEqual(len(audit(root, ['real'])), 2)

    def test_errors(self):
        self.assertEqual(self.run_cli('/nonexistent-r138-directory')[0],1)
        with contextlib.redirect_stderr(io.StringIO()): self.assertEqual(main(['bogus']),1)

if __name__ == '__main__': unittest.main()
