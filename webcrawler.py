from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CrawlResult, BrowserConfig, CacheMode
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy, BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter, ContentTypeFilter, ContentRelevanceFilter
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from typing import List

async def find_contact_url(start_url: str):
    
    contact_keywords = ['contact', 'get-in-touch', '/en-us/contact', 'contact/', '/contact-us']
    url_filter = URLPatternFilter(patterns=[f"*{cw}*" for cw in contact_keywords])
    keyword_scorer = KeywordRelevanceScorer(keywords=contact_keywords, weight=0.9)
    content_type = ContentTypeFilter(allowed_types=['text/html'])
    
    browser_config = BrowserConfig(
        verbose=True
    )
    
    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=1,
            include_external=False,
            url_scorer=keyword_scorer,
            filter_chain=FilterChain([url_filter, content_type]),
            max_pages=2
        ),
        scraping_strategy=LXMLWebScrapingStrategy(),
        cache_mode=CacheMode.BYPASS,
        exclude_all_images=True,
        locale="en-US",
        verbose=True,
        stream=False,
        check_robots_txt=True,
        mean_delay=1.0,
        max_range=2.0,
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:

        results: List[CrawlResult] = await crawler.arun(start_url, config=config)
        
        print(f"Crawled {len(results)} pages in total")
        
        for result in results:
            if result.success:
                print(f"URL: {result.url}")
                print(f"Success: {result.status_code}")
                print(f"Depth: {result.metadata.get('depth')}")
                print(f"Title: {result.metadata.get('title')}\n\n")
            else:
                print(f"{result.url} Error: {result.error_message}")
                

        # Return markdown from the last successful result
        return results[-1].markdown


