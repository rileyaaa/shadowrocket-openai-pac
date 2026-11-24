from pathlib import Path
from datetime import date
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
        self.assertIn('foo.invalid.test', doc.observed_hosts(html) - set(hosts))
        self.assertNotIn('tracker.fake.com', doc.observed_hosts(html))
    def test_two_label_claude_hosts_are_extracted(self):
        html = '<html><body>claude.ai claude.com api.anthropic.com browser-intake-us5-datadoghq.com</body></html>'
        hosts = doc.extract_hosts(html, 'claude')
        self.assertIn('claude.ai', hosts)
        self.assertIn('claude.com', hosts)
        self.assertIn('browser-intake-us5-datadoghq.com', hosts)
        self.assertIn('cdn.claudemcpcontent.com', doc.extract_hosts(html + ' cdn.claudemcpcontent.com', 'claude'))

    def test_bad_docs_never_publish(self):
        with self.assertRaises(ValueError):
            doc.extract_hosts('<html><p>hello</p></html>','gemini')
        with self.assertRaises(ValueError):
            doc.extract_hosts('<html><p>api.anthropic.com</p></html>','claude')
    def test_official_sources_are_bounded_and_are_advisory(self):
        self.assertEqual(set(doc.SOURCES),{'gemini_app_firewall','claude_code_network'})
        self.assertTrue(all(url.startswith('https://') for url, _ in doc.SOURCES.values()))

    def test_weekly_failure_catches_up_on_monday(self):
        self.assertTrue(doc.scheduled_due(date(2027,5,24),'schedule',{'checked_on':'2027-05-16'}))
        self.assertFalse(doc.scheduled_due(date(2027,5,25),'schedule',{'checked_on':'2027-05-24'}))
        self.assertFalse(doc.scheduled_due(date(2027,5,24),'push',None))

    def test_wildcard_scope_is_not_exact_host_coverage(self):
        self.assertIn('*.api.claude.com', doc.extract_hosts('claude.ai claude.com *.api.claude.com', 'claude'))
        approved = {'shadowrocket_ai':{'claude':['DOMAIN,api.claude.com']},
                    'v2rayn':{'claude':['DOMAIN-SUFFIX,claude.com']}}
        uncovered = doc.coverage_for('claude', ['api.claude.com','*.api.claude.com'], approved)
        self.assertEqual(uncovered['shadowrocket_ai'], ['*.api.claude.com'])
        self.assertEqual(uncovered['v2rayn'], [])

if __name__=='__main__': unittest.main()
