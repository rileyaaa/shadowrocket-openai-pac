from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_ai_docs as doc

class OfficialDocsAuditTests(unittest.TestCase):
    def test_extract_first_party_only_from_docs_text(self):
        html='<html><script>tracker.fake.com</script><body>' + ' '.join(
            ['gemini.google.com','jnn-pa.googleapis.com','accounts.google.com','ssl.gstatic.com',
             'www.googleapis.com','lh3.googleusercontent.com','optimizationguide-pa.googleapis.com',
             'play.google.com','fonts.googleapis.com','www.google.com','foo.invalid.test']) + '</body></html>'
        hosts=doc.extract_hosts(html,'gemini')
        self.assertIn('gemini.google.com',hosts)
        self.assertNotIn('tracker.fake.com',hosts)
        self.assertNotIn('foo.invalid.test',hosts)
    def test_bad_docs_never_publish(self):
        with self.assertRaises(ValueError):
            doc.extract_hosts('<html><p>hello</p></html>','gemini')
        with self.assertRaises(ValueError):
            doc.extract_hosts('<html><p>api.anthropic.com</p></html>','claude')
    def test_official_sources_are_bounded_and_are_advisory(self):
        self.assertEqual(set(doc.SOURCES),{'gemini_app_firewall','claude_code_network'})
        self.assertTrue(all(url.startswith('https://') for url, _ in doc.SOURCES.values()))

if __name__=='__main__': unittest.main()
