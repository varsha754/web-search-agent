"""
Content processing and extraction - minimal token usage
Token usage: Only for LLM-based extraction (optional)
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
import time
import trafilatura
from readability import Document
from newspaper import Article
import re
from tenacity import retry, stop_after_attempt, wait_exponential

from config import config


class ContentProcessor:
    """
    Extract and clean content from web pages
    Token usage: 0 (no LLM for basic extraction)
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.max_content_length = config.MAX_CONTENT_LENGTH
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    def fetch_html(self, url: str, timeout: int = 15) -> Optional[str]:
        """Fetch HTML content from URL"""
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            return response.text
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            return None
    
    def extract_readable_content(self, html: str, url: str) -> Tuple[str, str]:
        """
        Extract main content using multiple strategies
        
        Returns:
            Tuple of (title, content)
        """
        title = ""
        content = ""
        
        # Strategy 1: Trafilatura (fast, good for articles)
        if config.EXTRACT_READABLE:
            try:
                extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
                if extracted:
                    content = extracted
                    # Try to get title from trafilatura
                    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                    if title_match:
                        title = title_match.group(1)
            except Exception:
                pass
        
        # Strategy 2: Readability (if trafilatura failed)
        if not content:
            try:
                doc = Document(html)
                title = doc.title()
                content = doc.summary()
            except Exception:
                pass
        
        # Strategy 3: BeautifulSoup fallback
        if not content:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove non-content elements
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
                tag.decompose()
            
            # Get title
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text()
            
            # Extract main content
            main_selectors = ['main', 'article', '.content', '#content', '.main-content', '.post-content']
            main_content = None
            
            for selector in main_selectors:
                main_content = soup.select_one(selector)
                if main_content:
                    break
            
            if main_content:
                content = main_content.get_text(separator=' ', strip=True)
            else:
                content = soup.get_text(separator=' ', strip=True)
        
        # Clean content
        content = self.clean_text(content)
        
        # Limit length
        if len(content) > self.max_content_length:
            content = content[:self.max_content_length] + "..."
        
        return title, content
    
    def clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common noise patterns
        noise_patterns = [
            r'cookie policy',
            r'privacy policy',
            r'terms of service',
            r'subscribe to our newsletter',
            r'follow us on',
            r'© \d{4}'
        ]
        
        for pattern in noise_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def extract_metadata(self, html: str, url: str) -> Dict:
        """Extract metadata from page"""
        soup = BeautifulSoup(html, 'html.parser')
        metadata = {}
        
        # Open Graph tags
        og_tags = ['og:title', 'og:description', 'og:image', 'og:type']
        for tag in og_tags:
            meta = soup.find('meta', property=tag)
            if meta:
                metadata[tag] = meta.get('content', '')
        
        # Standard meta tags
        meta_tags = ['description', 'keywords', 'author']
        for tag in meta_tags:
            meta = soup.find('meta', {'name': tag})
            if meta:
                metadata[tag] = meta.get('content', '')
        
        # Canonical URL
        canonical = soup.find('link', rel='canonical')
        if canonical:
            metadata['canonical_url'] = canonical.get('href', '')
        
        # Publication date
        date_patterns = ['date', 'published', 'article:published_time']
        for pattern in date_patterns:
            meta = soup.find('meta', {'name': re.compile(pattern, re.I)})
            if not meta:
                meta = soup.find('meta', {'property': re.compile(pattern, re.I)})
            if meta:
                metadata['published_date'] = meta.get('content', '')
                break
        
        return metadata
    
    def process_batch(self, urls: List[str], delay: float = 1.0) -> List[Dict]:
        """Process multiple URLs"""
        results = []
        
        for i, url in enumerate(urls):
            print(f"  [{i+1}/{len(urls)}] Processing: {url[:60]}...")
            
            html = self.fetch_html(url)
            if html:
                title, content = self.extract_readable_content(html, url)
                metadata = self.extract_metadata(html, url)
                
                results.append({
                    'url': url,
                    'title': title,
                    'content': content,
                    'metadata': metadata,
                    'content_length': len(content)
                })
            
            if i < len(urls) - 1:
                time.sleep(delay)
        
        return results


# Example usage
if __name__ == "__main__":
    processor = ContentProcessor()
    html = processor.fetch_html("https://www.magicbricks.com/real-estate-news")
    if html:
        title, content = processor.extract_readable_content(html, "")
        print(f"Title: {title}")
        print(f"Content length: {len(content)}")
