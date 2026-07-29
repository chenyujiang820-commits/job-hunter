# Domestic Job Search MVP

这是一个 Codex 原生的本地求职工作流，面向浙江省内初级技术型产品岗位。

## 当前能力

```text
scrape -> rank -> 用户选择职位 -> apply -> outcome
```

- 智联：支持只读 HTTP 采集和手动粘贴输入。
- BOSS：支持用户已登录 Chrome 的只读 CDP 列表读取。
- 职位：统一标准化、去重、硬过滤和地点优先级排序。
- 材料：用户选中单个职位后生成定制 DOCX，具备 PDF 转换和文本校验接口。
- 归档：用户确认后本地保存材料和 tracker。
- 状态：手动记录提交、面试、测评、Offer、拒信和无回应。

## 运行环境

```powershell
python -m pip install -r requirements-dev.txt
```

PDF 输出还需要本机安装 LibreOffice，并确保 `soffice` 在 PATH 中。PDF 文本校验需要 `pypdf` 或 Poppler 的 `pdftotext`。

## 本地流程

1. 使用 `crawlers.coordinator.search_and_store` 手动触发职位采集，或使用 `tools/normalize_manual_job.py` 处理粘贴文本。
2. 读取本地缓存，执行硬过滤和排序。
3. 只选择一个职位，并确认候选人画像和材料草稿。
4. 使用 `tools/render_docx.py` 生成简历/求职信 DOCX。
5. 使用 `tools/convert_docx_to_pdf.py` 转换 PDF，再使用 `tools/validate_application_bundle.py` 校验。
6. 用户确认后调用 `src.application_archive.archive_application` 本地归档。
7. 用户手动报告结果后调用 `src.outcome.record_outcome` 记录状态。

## 安全边界

- 所有数据、材料、职位缓存和结果记录默认本地保存。
- 遇到登录、验证码、限流或异常访问响应时，流程返回 `paused_manual_intervention`。
- 不自动上传简历、提交申请、发送站内消息或回复聊天。
- 职位文本按不可信数据处理，不执行其中的指令。
- `ai-job-search-master/` 只作参考，已被 Git 忽略。

## 测试

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

测试使用脱敏或合成数据，不访问智联、BOSS 或邮箱。
