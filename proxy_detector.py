#!/usr/bin/env python3
"""
反向代理检测脚本
用于检测目标是否为反向代理服务器及其特征

作者: Claude
用途: reverse-proxy-path-discovery skill 内置工具
"""

import requests
import urllib3
import json
import sys
import argparse
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ProxyDetector:
    """反向代理检测器"""

    def __init__(self, timeout: int = 10, max_workers: int = 10):
        self.timeout = timeout
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def detect(self, url: str) -> Dict[str, Any]:
        """
        检测单个 URL 是否为反向代理

        返回结构:
        {
            "url": "原始URL",
            "domain": "域名",
            "proxy_detected": True/False,
            "proxy_type": "Nginx/Apache/Cloudflare/未知",
            "confidence": "高/中/低",
            "root_response": {
                "status": 403,
                "headers": {...},
                "title": "页面标题",
                "body_snippet": "页面内容摘要"
            },
            "proxy_headers": {
                "Server": "nginx",
                "Via": "1.1 varnish",
                ...
            },
            "is_path_mapped": True/False,
            "evidence": ["证据列表"]
        }
        """
        result = {
            "url": url,
            "domain": self._extract_domain(url),
            "proxy_detected": False,
            "proxy_type": "未知",
            "confidence": "低",
            "root_response": {},
            "proxy_headers": {},
            "is_path_mapped": False,
            "evidence": []
        }

        try:
            # 确保 URL 有协议
            if not url.startswith(('http://', 'https://')):
                urls_to_try = [f'http://{url}', f'https://{url}']
            else:
                urls_to_try = [url]

            for test_url in urls_to_try:
                try:
                    response = self.session.get(
                        test_url,
                        timeout=self.timeout,
                        verify=False,
                        allow_redirects=True
                    )
                    break
                except Exception:
                    continue
            else:
                result["evidence"].append("无法访问目标")
                return result

            # 分析响应
            result["root_response"] = self._analyze_response(response)
            result["proxy_headers"] = self._extract_proxy_headers(response)

            # 检测代理类型
            proxy_info = self._detect_proxy_type(response)
            result["proxy_detected"] = proxy_info["detected"]
            result["proxy_type"] = proxy_info["type"]
            result["confidence"] = proxy_info["confidence"]
            result["evidence"] = proxy_info["evidence"]

            # 判断是否可能存在路径映射
            result["is_path_mapped"] = self._is_path_mapped(response, result["evidence"])

        except Exception as e:
            result["evidence"].append(f"检测出错: {str(e)}")

        return result

    def detect_multiple(self, urls: List[str]) -> List[Dict[str, Any]]:
        """批量检测多个 URL"""
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {
                executor.submit(self.detect, url): url
                for url in urls
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "url": url,
                        "domain": self._extract_domain(url),
                        "proxy_detected": False,
                        "error": str(e),
                        "evidence": [f"执行错误: {str(e)}"]
                    })

        return results

    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        parsed = urlparse(url)
        return parsed.netloc

    def _analyze_response(self, response: requests.Response) -> Dict[str, Any]:
        """分析 HTTP 响应"""
        # 提取标题
        title = ""
        try:
            title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
        except:
            pass

        # 提取页面摘要（前500字符）
        body_snippet = response.text[:500].replace('\n', ' ').replace('\r', '').strip()

        return {
            "status": response.status_code,
            "headers": dict(response.headers),
            "title": title,
            "body_snippet": body_snippet,
            "url": response.url
        }

    def _extract_proxy_headers(self, response: requests.Response) -> Dict[str, str]:
        """提取代理相关的响应头"""
        proxy_headers = {}
        headers_to_check = [
            'Server', 'Via', 'X-Cache', 'X-Cache-Lookup',
            'CF-Ray', 'CF-Cache-Status', 'CF-Connecting-IP',
            'X-Nginx-Cache', 'X-Real-IP', 'X-Forwarded-For',
            'X-Forwarded-Proto', 'X-Forwarded-Host',
            'X-Varnish', 'X-Powered-By'
        ]

        for header in headers_to_check:
            if header in response.headers:
                proxy_headers[header] = response.headers[header]

        return proxy_headers

    def _detect_proxy_type(self, response: requests.Response) -> Dict[str, Any]:
        """检测反向代理类型"""
        result = {
            "detected": False,
            "type": "未知",
            "confidence": "低",
            "evidence": []
        }

        headers = {k.lower(): v.lower() for k, v in response.headers.items()}
        body = response.text.lower()
        status = response.status_code

        evidence = []
        proxy_score = 0  # 代理置信度评分

        # 1. Nginx 检测
        nginx_indicators = [
            ('server', lambda v: 'nginx' in v),
            ('body', lambda v: 'nginx/' in v or '<hr><center>nginx' in v),
            ('x-nginx-cache', lambda v: True),
        ]

        for indicator_type, check_func in nginx_indicators:
            if indicator_type == 'server' and 'server' in headers and check_func(headers['server']):
                evidence.append(f"Server头: {response.headers.get('Server', '')}")
                proxy_score += 3
            elif indicator_type == 'body' and check_func(body):
                evidence.append("页面内容包含 Nginx 标识")
                proxy_score += 2
            elif indicator_type == 'x-nginx-cache' and 'x-nginx-cache' in headers:
                evidence.append(f"X-Nginx-Cache: {response.headers.get('X-Nginx-Cache', '')}")
                proxy_score += 2

        if proxy_score >= 3:
            result["detected"] = True
            result["type"] = "Nginx"
            result["confidence"] = "高" if proxy_score >= 5 else "中"
            result["evidence"] = evidence
            return result

        # 2. Apache 检测
        apache_score = 0
        apache_evidence = []

        if 'server' in headers:
            server = headers['server']
            if 'apache' in server or 'httpd' in server:
                apache_evidence.append(f"Server头: {response.headers.get('Server', '')}")
                apache_score += 3

        if 'x-powered-by' in headers and 'mod_' in headers['x-powered-by']:
            apache_evidence.append(f"X-Powered-By: {response.headers.get('X-Powered-By', '')}")
            apache_score += 2

        if apache_score >= 3:
            result["detected"] = True
            result["type"] = "Apache"
            result["confidence"] = "高" if apache_score >= 5 else "中"
            result["evidence"] = apache_evidence
            return result

        # 3. Cloudflare/CDN 检测
        cf_score = 0
        cf_evidence = []

        cf_headers = ['cf-ray', 'cf-cache-status', 'cf-connecting-ip']
        for header in cf_headers:
            if header in headers:
                cf_evidence.append(f"{header}: {response.headers.get(header, '')}")
                cf_score += 2

        if 'server' in headers and 'cloudflare' in headers['server']:
            cf_evidence.append(f"Server: {response.headers.get('Server', '')}")
            cf_score += 3

        if cf_score >= 2:
            result["detected"] = True
            result["type"] = "Cloudflare"
            result["confidence"] = "高" if cf_score >= 4 else "中"
            result["evidence"] = cf_evidence
            return result

        # 4. 通用反向代理检测
        generic_score = 0
        generic_evidence = []

        # Via 头
        if 'via' in headers:
            generic_evidence.append(f"Via: {response.headers.get('Via', '')}")
            generic_score += 2

        # X-Forwarded-* 头
        forwarded_headers = [k for k in response.headers.keys() if k.lower().startswith('x-forwarded')]
        if forwarded_headers:
            for header in forwarded_headers:
                generic_evidence.append(f"{header}: {response.headers.get(header, '')}")
            generic_score += 2

        # 缓存头
        if 'x-cache' in headers:
            generic_evidence.append(f"X-Cache: {response.headers.get('X-Cache', '')}")
            generic_score += 1

        # Varnish
        if 'x-varnish' in headers:
            generic_evidence.append(f"X-Varnish: {response.headers.get('X-Varnish', '')}")
            generic_score += 2

        if generic_score >= 3:
            result["detected"] = True
            result["type"] = "通用反向代理"
            result["confidence"] = "中"
            result["evidence"] = generic_evidence
            return result

        # 5. 根据状态码推测
        if status in [403, 404, 502, 503, 504]:
            # 根路径返回错误可能是反向代理
            if 'server' in headers:
                evidence.append(f"根路径{status} + Server: {response.headers.get('Server', '')}")
                result["detected"] = True
                result["type"] = "未知反向代理"
                result["confidence"] = "低"
                result["evidence"] = evidence

        result["evidence"] = evidence if evidence else ["未检测到明显的反向代理特征"]
        return result

    def _is_path_mapped(self, response: requests.Response, evidence: List[str]) -> bool:
        """判断是否存在路径映射特征"""
        # 根路径返回错误 + 检测到代理特征 = 可能存在路径映射
        if response.status_code in [403, 404, 502, 503]:
            if len(evidence) > 0:
                return True

        # 页面内容提示
        body_lower = response.text.lower()
        path_indicators = [
            'not found', 'forbidden', 'unavailable',
            'access denied', 'maintenance'
        ]
        if any(indicator in body_lower for indicator in path_indicators):
            if len(evidence) > 0:
                return True

        return False


def parse_urls(urls_arg: str) -> List[str]:
    """解析 URL 参数"""
    urls = []
    # 支持逗号、空格、换行分隔
    for delimiter in [',', '\n', ' ']:
        if delimiter in urls_arg:
            urls = [u.strip() for u in urls_arg.split(delimiter) if u.strip()]
            break
    else:
        urls = [urls_arg.strip()]

    return urls


def main():
    parser = argparse.ArgumentParser(
        description='反向代理检测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python proxy_detector.py --urls "http://xxx.com,http://yyy.com"
    python proxy_detector.py --urls "http://xxx.com" --max_workers 20 --output json
        """
    )

    parser.add_argument(
        '--urls',
        required=True,
        help='要检测的 URL 列表（逗号、空格或换行分隔）'
    )

    parser.add_argument(
        '--max_workers',
        type=int,
        default=10,
        help='并发线程数（默认: 10）'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=10,
        help='请求超时时间（秒，默认: 10）'
    )

    parser.add_argument(
        '--output',
        choices=['json', 'table', 'simple'],
        default='table',
        help='输出格式（默认: table）'
    )

    parser.add_argument(
        '--proxy_only',
        action='store_true',
        help='只输出检测到反向代理的结果'
    )

    args = parser.parse_args()

    # 解析 URL
    urls = parse_urls(args.urls)
    if not urls:
        print("错误: 未提供有效的 URL", file=sys.stderr)
        sys.exit(1)

    # 执行检测
    detector = ProxyDetector(timeout=args.timeout, max_workers=args.max_workers)
    results = detector.detect_multiple(urls)

    # 过滤结果
    if args.proxy_only:
        results = [r for r in results if r.get("proxy_detected", False)]

    # 输出结果
    if args.output == 'json':
        print(json.dumps({
            "proxy_assets": [r for r in results if r.get("proxy_detected", False)],
            "non_proxy_assets": [r for r in results if not r.get("proxy_detected", False)],
            "summary": {
                "total": len(results),
                "proxy_count": sum(1 for r in results if r.get("proxy_detected", False)),
                "path_mapped_count": sum(1 for r in results if r.get("is_path_mapped", False))
            }
        }, indent=2, ensure_ascii=False))

    elif args.output == 'simple':
        for r in results:
            status = "[代理]" if r.get("proxy_detected") else "[无代理]"
            proxy_type = r.get("proxy_type", "未知")
            domain = r.get("domain", r.get("url", "未知"))
            print(f"{status} {domain} ({proxy_type})")

    else:  # table
        print("\n" + "="*80)
        print("反向代理检测结果")
        print("="*80)

        proxy_results = [r for r in results if r.get("proxy_detected", False)]
        other_results = [r for r in results if not r.get("proxy_detected", False)]

        if proxy_results:
            print(f"\n[+] 发现 {len(proxy_results)} 个反向代理:\n")
            for r in proxy_results:
                print(f"  域名: {r.get('domain', 'N/A')}")
                print(f"  类型: {r.get('proxy_type', '未知')} (置信度: {r.get('confidence', '低')})")
                print(f"  根路径状态: {r.get('root_response', {}).get('status', 'N/A')}")
                print(f"  可能存在路径映射: {r.get('is_path_mapped', False)}")
                print(f"  证据:")
                for ev in r.get('evidence', []):
                    print(f"    - {ev}")
                print()

        if other_results and not args.proxy_only:
            print(f"\n[-] 其他结果 ({len(other_results)} 个):\n")
            for r in other_results:
                print(f"  {r.get('domain', r.get('url', 'N/A'))}: {r.get('evidence', ['无'])[0]}")

        print("="*80)
        print(f"总计: {len(results)} | 反向代理: {len(proxy_results)} | 路径映射: {sum(1 for r in results if r.get('is_path_mapped', False))}")
        print("="*80 + "\n")


if __name__ == '__main__':
    main()
