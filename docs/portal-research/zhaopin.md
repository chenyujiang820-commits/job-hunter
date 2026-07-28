# 智联招聘访问研究记录

## Research date

2026-07-28。调查范围限定为未登录、无 Cookie、无 Token 的公开 HTTP GET；没有提交表单、登录、验证码交互、分页遍历或批量抓取。

## Search entry

- Public entry: `https://www.zhaopin.com/sou/jl{city_code}?kw={urlencoded_keyword}`
- Observed city codes from the public city map: 丽水 `663`、杭州 `653`、金华 `659`。
- Observed target sample: `https://www.zhaopin.com/sou/jl663?kw=%E4%BA%A7%E5%93%81%E7%BB%8F%E7%90%86`
- Query parameter: `kw` is the keyword; the city is encoded in the `jl` path segment.
- Pagination observation: the public result page exposed `/p1`, `/p2` style links on one sample page.
- Recency parameter: no current, documented public parameter was verified. Do not invent or send undocumented query parameters.
- Legacy reference: the city map exposed `sou.zhaopin.com/Jobs/searchresult.ashx?jl=...&sm=0&p=1&sf=0`, but it was not used for automation because it is query-based and its current contract was not verified.

## Detail entry

- Public detail pattern: `https://www.zhaopin.com/jobdetail/<job-id>.htm`
- Observed sample: `https://www.zhaopin.com/jobdetail/CC581375020J40919143515.htm`
- Detail pages returned server-rendered HTML in the bounded sample. The page contained the normalized field anchors listed below.

## Search public status

YES for a bounded unauthenticated GET observation. The Lishui sample returned HTTP 200, a title containing “丽水产品经理招聘”, and three detail-link occurrences. The page shell contained a login/register link, but the sampled GET did not redirect to login or show a CAPTCHA.

This technical observation is not permission to automate access.

## Detail public status

YES for a bounded unauthenticated GET observation. The sampled detail page returned HTTP 200 and contained job/company/location/qualification markers without a CAPTCHA or login redirect. A login link in the common page shell was present but was not required for the sampled GET.

## Field anchors

The public HTML samples contained these anchors. They are recorded for future manual normalization only; no parser should be implemented against the live site under the current access decision.

| Normalized field | Observed anchor or source | Confidence |
| --- | --- | --- |
| `id` | `/jobdetail/<job-id>.htm`, `jobId`, `positionId` | high |
| `title` | HTML title and job heading | high |
| `company` | `companyName` and company detail link | high |
| `location` | `工作地点` and city context | medium |
| `salary` | `salary` and salary text | medium |
| `experience` | `工作经验` | high |
| `education` | `学历` | high |
| `date` | search/detail metadata; exact stable anchor not verified | low |
| `url` | canonical `/jobdetail/<job-id>.htm` link | high |
| `source` | fixed value `zhaopin` | high |

## Response observations

- Lishui keyword sample: HTTP 200, 62,395-byte HTML response, three detail-link occurrences, no CAPTCHA marker.
- Detail sample: HTTP 200, 1,259,107-byte HTML response, field anchors present, no CAPTCHA marker.
- These sizes and counts are observations only, not rate-limit or completeness guarantees.
- No raw live response was saved. The fixture directory contains only redacted field shapes.

## robots.txt

- `https://www.zhaopin.com/robots.txt`: HTTP 200. For `User-agent: *`, it disallows `/user/*`, `/source/*`, `/install/*`, `/data/*`, `/*.js*`, `*?*`, `*/api/*`, `/*.json*`, recommendation/resume/schedule/position paths, and several tracking/query variants including `provinceCode` and `cityCode`.
- `https://sou.zhaopin.com/robots.txt`: HTTP 200. It disallows user/source/install/data paths, JavaScript, and selected tracking query parameters.
- The current canonical search URL is under `www.zhaopin.com` and uses a query parameter, so it falls under the `www` generic `*?*` prohibition.

## Service terms

- Legal hub observed at `https://rd6.zhaopin.com/aboutus/legal`; the current service agreement resolved to `https://rd6.zhaopin.com/aboutus/legal/service`.
- The page identified itself as `智联平台用户服务协议`; observed update date was 2026-07-02 and effective date was 2026-07-15.
- The agreement applies to registered and non-registered use, including browsing.
- The job-seeker rules prohibit using the service for non-job-search purposes, unauthorized copying/forwarding of personal or employer information, and contacting publishers without consent.
- The security section explicitly identifies spiders, crawlers, simulated-person programs, automated scripts, data-mining tools, and non-normal browsing as prohibited categories when they read/copy/store platform data or evade technical measures.
- The agreement states users must follow the platform Robots protocol and must not access or collect platform content in the prohibited manner without prior written consent.
- A separate clause states that platform content may not be used for AI/ML model training, development, testing, optimization, fine-tuning, or deployment without prior written permission.
- This is a product-risk record, not legal advice. Written permission or an approved official API would be required before reconsidering automated access.

## Access requirements

- No account, Cookie, Token, SMS verification, or CAPTCHA was used in the bounded observations.
- The public page shell contains login/register controls, and this must not be interpreted as authorization to automate.
- Stop immediately if a future manual inspection shows login, CAPTCHA, SMS, anti-bot, rate-limit, or abnormal-response behavior.

## Rate-limit observations

No numeric public rate limit was found. No load, concurrency, retry, pagination sweep, or stress test was performed. Because the access decision is not to automate, the project must not infer a safe request rate from these observations.

## Access decision

Access decision: MANUAL_URL_ONLY

The technical surface is readable, but automated search/detail access is not approved under the observed Robots rules and service agreement. Do not implement a live Zhilian parser or CLI in this MVP. The supported flow is:

1. The user manually opens a job page on Zhilian.
2. The user supplies the URL and, when needed, copies the visible job text into the local workflow.
3. Codex treats the supplied text as untrusted input and performs local normalization, filtering, ranking, and material generation only after the existing confirmation gates.

An official, written permission or approved public API would be a new prerequisite for changing this decision.
