# Upstream sources and attribution

Generated routing and ad data retain their respective upstream notices. The original Python builder, configuration templates and documentation in this project are provided for this task; upstream data is not relicensed by this file.

| Project | Use | Upstream license copy |
| --- | --- | --- |
| blackmatrix7/ios_rule_script | Service routing, Direct/LAN, AdvertisingLite domains | `licenses/blackmatrix7-GPL-2.0.txt` |
| Loyalsoldier/surge-rules | CN/proxy/GFW domains and CN IP | `licenses/Loyalsoldier-GPL-3.0.txt` |
| privacy-protection-tools/anti-AD | Advertising and tracker domains | `licenses/anti-AD-MIT.txt` |

The source repositories also aggregate data from other rule projects. Retain source attribution and consult their notices when redistributing derived lists.

## Exact fetch inputs

| ID | Target | Format | URL |
| --- | --- | --- | --- |
| bm_Direct | unbreak | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Direct/Direct.list |
| bm_Lan | lan | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Lan/Lan.list |
| bm_OpenAI | openai | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/OpenAI/OpenAI.list |
| bm_Claude | claude | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Claude/Claude.list |
| bm_Anthropic | claude | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Anthropic/Anthropic.list |
| bm_Gemini | gemini | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Gemini/Gemini.list |
| bm_Telegram | telegram | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Telegram/Telegram.list |
| bm_Netflix | netflix | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Netflix/Netflix.list |
| bm_YouTube | youtube | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/YouTube/YouTube.list |
| bm_Disney | disney | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Disney/Disney.list |
| bm_Apple | apple | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Apple/Apple.list |
| bm_Apple_domains | apple | domains | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Apple/Apple_Domain.list |
| bm_Microsoft | microsoft | rules | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/Microsoft/Microsoft.list |
| loyal_direct | cn-domain | domains | https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/direct.txt |
| loyal_proxy | proxy | domains | https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/proxy.txt |
| loyal_gfw | proxy | domains | https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/gfw.txt |
| loyal_cncidr | cn-ip | rules | https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/cncidr.txt |
| antiad | adblock | rules | https://raw.githubusercontent.com/privacy-protection-tools/anti-AD/master/anti-ad-surge.txt |
| bm_ad_domains | adblock | domains | https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/AdvertisingLite/AdvertisingLite_Domain.list |

## Manually reviewed rewrite endpoints

The narrow rewrite patterns were selected with reference to blackmatrix7’s rewrite collection. v2 also references its Zhihu endpoint definitions and fmz200's Weibo feed schemas. No wholesale AllInOne import, third-party executable script download, VIP/account modifications, or broad MITM list is included.

https://github.com/blackmatrix7/ios_rule_script/tree/master/rewrite/Shadowrocket/AllInOne

Endpoint/schema references reviewed on 2026-10-18:

- https://github.com/blackmatrix7/ios_rule_script/blob/master/script/zheye/zheye.snippet
- https://github.com/blackmatrix7/ios_rule_script/tree/master/script/zheye
- https://github.com/fmz200/wool_scripts/blob/main/Loon/plugin/weibo.plugin
- https://github.com/fmz200/wool_scripts/blob/main/Scripts/weibo/weibo_main.js
- https://github.com/fmz200/wool_scripts/blob/main/Scripts/weibo/weibo_ads.js

`scripts/domestic-ads.js` is a small, local implementation using those documented API paths and explicit advertising fields. It is not a conversion or full copy of those scripts. Its deployed content digest is recorded in `manifest.json`; this review date does not imply upstream schemas or all app versions have been tested.

For exact fetched content hashes, times, and upstream version comments, see `manifest.json`. A fetch date is not a maintenance date.
