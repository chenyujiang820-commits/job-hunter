# Search Queries

搜索由用户人工触发，仅接收用户提供的智联招聘 URL 和页面上可见的职位文本。流程不抓取、不自动访问智联页面。

人工边界：不访问登录、不访问验证码或反爬页面；只处理用户已经打开并粘贴的公开可见内容。

## Query Order

1. 丽水: junior product manager terms and Chinese synonyms.
2. 杭州 and 金华: junior product manager terms and Chinese synonyms.
3. Other Zhejiang cities: junior product manager terms and Chinese synonyms.

Use Chinese role and city synonyms as appropriate during manual inspection. Cache only the inspected results locally, deduplicate them, and do not access login-only or anti-bot content. Do not access login-only or anti-bot content.
