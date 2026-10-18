import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("builder", Path(__file__).parents[1] / "scripts/build.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class RuleBehaviorTests(unittest.TestCase):
    def test_domain_set_does_not_turn_exact_host_into_suffix(self):
        rules, _ = b.parse("exact.example\n.example.net\n+.example.org\n", "domains")
        self.assertEqual(rules, {("DOMAIN", "exact.example"),
                                 ("DOMAIN-SUFFIX", "example.net"),
                                 ("DOMAIN-SUFFIX", "example.org")})

    def test_suffix_deduplication_respects_label_boundaries(self):
        result = b.minimize({("DOMAIN-SUFFIX", "example.com"),
                             ("DOMAIN", "a.example.com"),
                             ("DOMAIN-SUFFIX", "b.example.com"),
                             ("DOMAIN", "notexample.com")})
        self.assertEqual(result, {("DOMAIN-SUFFIX", "example.com"),
                                  ("DOMAIN", "notexample.com")})

    def test_allow_child_removes_parent_suffix_reject(self):
        ads = {("DOMAIN-SUFFIX", "example.com"),
               ("DOMAIN", "ads.other.com")}
        kept, removed = b.remove_protected(ads, {("DOMAIN", "login.example.com")})
        self.assertEqual(kept, {("DOMAIN", "ads.other.com")})
        self.assertEqual(removed, [("DOMAIN-SUFFIX", "example.com")])

    def test_allow_parent_removes_child_reject(self):
        kept, _ = b.remove_protected({("DOMAIN", "api.pay.example")},
                                     {("DOMAIN-SUFFIX", "pay.example")})
        self.assertFalse(kept)

    def test_keyword_cannot_override_explicit_allow_domain(self):
        kept, _ = b.remove_protected({("DOMAIN-KEYWORD", "analytics")},
                                     {("DOMAIN", "analytics.payment.example")})
        self.assertFalse(kept)

    def test_ipv4_ipv6_and_asn_all_get_no_resolve(self):
        rules, _ = b.parse("IP-CIDR,1.2.3.4/24\nIP-CIDR6,2001:db8::/32\nIP-ASN,62041", "rules")
        lines = b.render_list("test", rules).decode().splitlines()
        self.assertTrue(all(x.endswith(",no-resolve") for x in lines if not x.startswith("#")))

    def test_wrong_format_and_html_abort_instead_of_empty_publication(self):
        with self.assertRaises(ValueError):
            b.parse("<html>CDN error</html>", "rules")
        with self.assertRaises(ValueError):
            b.parse("DOMAIN-SUFFIX,example.com", "domains")
        with self.assertRaises(ValueError):
            b.parse("UNKNOWN,example.com", "rules")

    def test_upstream_policy_cannot_inject_direct_into_adblock(self):
        with self.assertRaises(ValueError):
            b.parse("DOMAIN-SUFFIX,example.com,DIRECT", "rules")

    def test_main_template_has_six_ordered_tiers_and_no_adblock_reference(self):
        text = (b.ROOT / "templates/routing.conf").read_text()
        positions = [text.index(s) for s in ["# 第一层", "# 第二层", "# 第三层",
                                            "# 第四层", "# 第五层", "# 第六层"]]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("RULE_adblock", text)


if __name__ == "__main__":
    unittest.main()
