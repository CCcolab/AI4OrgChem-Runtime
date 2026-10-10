"""User operation paths and export safeguards. Browser receipts remain separate."""
from html import unescape
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


class WebDeliveryContractTests(unittest.TestCase):
    def setUp(self):self.page=(ROOT/'docs/index.html').read_text('utf-8')

    def code(self,ident):
        return unescape(re.search(r'<code[^>]*id="'+ident+r'"[^>]*>(.*?)</code>',self.page,re.S).group(1))

    def test_clone_and_same_installation_record_in_the_entire_ordinary_path(self):
        install=self.code('source-install-command')
        self.assertIn('git clone https://github.com/CCcolab/AI4OrgChem-Runtime.git',install)
        self.assertIn('git rev-parse HEAD',install)
        record=r'..\installations\molecular-service\installation-record.json'
        for ident in ['source-install-command','single-point-command','single-point-custom-command']:
            code=self.code(ident)
            self.assertIn('run-installed-runtime.py --installation-record '+record,code)
            self.assertIn('--task single-point',code)
            self.assertNotIn('start-molecular-service.ps1',code)
        self.assertIn(r'D:\chem-work\runtime-install\runtime',self.code('single-point-location-command'))
        self.assertIn('ordinary-candidate-history',self.page)

    def test_original_scientific_input_templates_remain_exact(self):
        for ident,path in [('single-point-request-json','examples/molecular-service/water/request.json'),
                           ('single-point-xyz-text','examples/molecular-service/water/molecule.xyz')]:
            self.assertEqual(self.code(ident).encode('utf-8'),(ROOT/path).read_bytes())

    def test_real_high_cost_parameter_and_current_professional_links(self):
        self.assertNotIn('-Task 多态约束结构优化',self.page)
        self.assertIn('-Task P11 -Mode live',self.page)
        self.assertIn('CURRENT_PROFESSIONAL_SERVICES_zh-CN.md',self.page)
        self.assertIn('current-delivery-20261010.json',self.page)
        self.assertIn('当前网页与实际下载身份',self.page)

    def test_head_guard_runs_before_and_after_clean_export(self):
        self.assertIn('Array.from(parsed.head.children)',self.page)
        self.assertIn('function assertExportHead',self.page)
        self.assertIn('assertExportHead(parsed)',self.page)
        self.assertIn('assertExportHead(out,parsed)',self.page)
        self.assertIn("assertExportHead(new DOMParser().parseFromString(html,'text/html'),out)",self.page)
        self.assertIn('cleanExport,assertExportHead,deliveryEntries',self.page)
        for selector in ['meta[charset]','meta[name="viewport"]','width=device-width']:
            self.assertIn(selector,self.page)


if __name__=='__main__':unittest.main()
