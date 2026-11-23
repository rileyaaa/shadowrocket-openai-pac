"""Verify the sole active Shadowrocket AI subscription and rule order."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_ai_shadowrocket as ai_builder


class DedicatedShadowrocketTests(unittest.TestCase):
    def test_ai_variant_is_independent_file_and_insertion_preserves_order(self):
        self.assertNotEqual(ai_builder.OUTPUT.name, 'Shadowrocket_Johnshall_OpenAI.conf')
        base = ('[General]\n[Rule]\nDOMAIN,chatgpt.com,RackNerd\n'
                + ai_builder.JOHNSHALL_MARKER + 'DOMAIN,google.com,DIRECT\nFINAL,direct\n')
        ai = {'rules': {'gemini': ['DOMAIN-SUFFIX,gemini.google.com',
                                  'DOMAIN,generativelanguage.googleapis.com'],
                        'claude': ['DOMAIN-SUFFIX,claude.ai',
                                   'DOMAIN-SUFFIX,anthropic.com',
                                   'DOMAIN,browser-intake-us5-datadoghq.com']}}
        result = ai_builder.insert_ai_rules(base, ai, 'RackNerd🇺🇸西雅图')
        self.assertIn('DOMAIN-SUFFIX,gemini.google.com,RackNerd🇺🇸西雅图,force-remote-dns',result)
        self.assertIn('DOMAIN-SUFFIX,claude.ai,RackNerd🇺🇸西雅图,force-remote-dns',result)
        self.assertIn('DOMAIN,browser-intake-us5-datadoghq.com,RackNerd🇺🇸西雅图,force-remote-dns',result)
        self.assertNotIn('DOMAIN-SUFFIX,datadoghq.com,RackNerd', result)
        self.assertTrue(result.index('DOMAIN,chatgpt.com,RackNerd') <
                        result.index('DOMAIN-SUFFIX,gemini.google.com,RackNerd') <
                        result.index('DOMAIN,google.com,DIRECT'))
        self.assertEqual(result.count('FINAL,direct'),1)
        self.assertEqual(base.count('DOMAIN-SUFFIX,gemini.google.com'),0)

    def test_strict_anchor_and_node(self):
        ai = {'rules': {'gemini': ['DOMAIN-SUFFIX,gemini.google.com'],
                        'claude': ['DOMAIN-SUFFIX,claude.ai']}}
        with self.assertRaises(ValueError):
            ai_builder.insert_ai_rules('[Rule]\nFINAL,direct',ai,'Seattle')
        with self.assertRaises(ValueError):
            ai_builder.insert_ai_rules(ai_builder.JOHNSHALL_MARKER,ai,'invalid,node')

if __name__ == '__main__':
    unittest.main()
