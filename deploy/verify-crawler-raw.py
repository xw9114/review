"""Verify the configured cleaner's raw-HTML API using synthetic public-style text."""
from app.integrations.crawl4ai import get_crawl4ai_connector
from app.integrations import article

connector = get_crawl4ai_connector()
synthetic = ("<article><h1>清洗连通性测试</h1><p>" + "这是本地构造的测试段落，不包含日记或用户资料。" * 5 + "</p><p>一阶矩与二阶矩用于描述梯度统计量。</p></article>").encode()
article.fetch_article_html = lambda _: (synthetic, "https://example.com/article")
try:
    result = connector.clean_article("https://example.com/article")
except Exception as exc:
    response = getattr(exc.__cause__, "response", None)
    if response is not None:
        print("Cleaner diagnostic:", response.status_code, response.text[:1200])
    raise
assert "一阶矩" in result and "清洗连通性测试" in result
print("PASS: configured Crawl4AI raw-HTML cleaning; synthetic content only; chars=", len(result))
