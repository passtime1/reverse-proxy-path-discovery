#!/usr/bin/env python3
"""
路径分析脚本
用于分析从 site: 搜索提取的 URL，发现二级路径映射

作者: Claude
用途: reverse-proxy-path-discovery skill 内置工具
"""

import json
import sys
import argparse
from urllib.parse import urlparse
from collections import Counter
from typing import Dict, List, Any


class PathAnalyzer:
    """URL 路径分析器"""

    # 路径类型定义
    PATH_PATTERNS = {
        '管理系统': {
            'patterns': ['admin', 'manage', 'console', 'dashboard', 'control', 'backend', 'cms'],
            'priority': '高',
            'stars': '⭐⭐⭐'
        },
        'API接口': {
            'patterns': ['api', 'v1', 'v2', 'v3', 'graphql', 'swagger', 'openapi', 'rest'],
            'priority': '高',
            'stars': '⭐⭐'
        },
        '测试环境': {
            'patterns': ['test', 'dev', 'staging', 'uat', 'demo', 'beta', 'alpha', 'preview'],
            'priority': '高',
            'stars': '⭐⭐⭐'
        },
        '前端应用': {
            'patterns': ['app', 'web', 'mobile', 'h5', 'pc', 'wap', 'm', 'www', 'main'],
            'priority': '中',
            'stars': '⭐⭐'
        },
        '门户系统': {
            'patterns': ['portal', 'gateway', 'entry', 'home', 'index', 'main', 'center'],
            'priority': '中',
            'stars': '⭐⭐'
        },
        '用户系统': {
            'patterns': ['user', 'account', 'profile', 'member', 'auth', 'login', 'sso'],
            'priority': '中',
            'stars': '⭐⭐'
        },
        '静态资源': {
            'patterns': ['static', 'assets', 'cdn', 'dist', 'build', 'res', 'resource'],
            'priority': '低',
            'stars': '⭐'
        },
        '备份系统': {
            'patterns': ['backup', 'bak', 'old', 'legacy', 'archive', 'history'],
            'priority': '高',
            'stars': '⭐⭐⭐'
        }
    }

    def __init__(self, min_frequency: int = 2):
        self.min_frequency = min_frequency

    def analyze(self, urls: List[str]) -> Dict[str, Any]:
        """分析 URL 列表，提取二级路径"""
        if not urls:
            return {
                "total_urls": 0,
                "domains": [],
                "path_frequency": {},
                "path_mappings": [],
                "statistics": {}
            }

        domains = self._extract_domains(urls)
        second_level_paths = self._extract_second_level_paths(urls)
        path_frequency = Counter(second_level_paths)

        filtered_paths = {
            path: count for path, count in path_frequency.items()
            if count >= self.min_frequency
        }

        path_mappings = []
        for path, frequency in sorted(filtered_paths.items(), key=lambda x: x[1], reverse=True):
            sample_urls = [
                url for url in urls
                if self._get_second_level_path(url) == path
            ][:5]

            system_info = self._classify_path(path)

            path_mappings.append({
                "path": path,
                "frequency": frequency,
                "sample_urls": sample_urls,
                "system_type": system_info['type'],
                "priority": system_info['priority'],
                "stars": system_info['stars']
            })

        return {
            "total_urls": len(urls),
            "domains": list(domains),
            "path_frequency": dict(path_frequency),
            "path_mappings": path_mappings,
            "statistics": {
                "total_urls": len(urls),
                "unique_paths": len(path_frequency),
                "filtered_paths": len(filtered_paths),
                "high_priority": sum(1 for p in path_mappings if p['priority'] == '高'),
                "medium_priority": sum(1 for p in path_mappings if p['priority'] == '中'),
                "low_priority": sum(1 for p in path_mappings if p['priority'] == '低')
            }
        }

    def _extract_domains(self, urls: List[str]) -> set:
        """从 URL 列表提取域名"""
        domains = set()
        for url in urls:
            try:
                if not url.startswith(('http://', 'https://')):
                    url = 'http://' + url
                parsed = urlparse(url)
                domains.add(parsed.netloc)
            except:
                pass
        return domains

    def _get_second_level_path(self, url: str) -> str:
        """从 URL 提取二级路径"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]

            if len(path_parts) >= 1:
                return f'/{path_parts[0]}/'
            return '/'
        except:
            return '/'

    def _extract_second_level_paths(self, urls: List[str]) -> List[str]:
        """从 URL 列表提取所有二级路径"""
        paths = []
        for url in urls:
            path = self._get_second_level_path(url)
            if path != '/':
                paths.append(path)
        return paths

    def _classify_path(self, path: str) -> Dict[str, str]:
        """根据路径名判断系统类型"""
        path_lower = path.lower().strip('/')

        for system_type, info in self.PATH_PATTERNS.items():
            for pattern in info['patterns']:
                if pattern in path_lower:
                    return {
                        'type': system_type,
                        'priority': info['priority'],
                        'stars': info['stars']
                    }

        return {
            'type': '未知系统',
            'priority': '低',
            'stars': '⭐'
        }


def parse_input(input_data: str) -> List[str]:
    """解析输入"""
    urls = []
    try:
        data = json.loads(input_data)
        if isinstance(data, list):
            urls = data
        elif isinstance(data, dict) and 'urls' in data:
            urls = data['urls']
    except:
        urls = [line.strip() for line in input_data.split('\n') if line.strip()]
    return urls


def main():
    parser = argparse.ArgumentParser(description='路径分析工具')
    parser.add_argument('--urls', help='URL 列表（JSON 格式）')
    parser.add_argument('--input-file', help='从文件读取 URL 列表')
    parser.add_argument('--min-frequency', type=int, default=2, help='最小出现频率')
    parser.add_argument('--top', type=int, default=20, help='显示前 N 个路径')
    parser.add_argument('--output', choices=['json', 'table', 'simple'], default='table', help='输出格式')
    args = parser.parse_args()

    urls = []
    if args.urls:
        urls = parse_input(args.urls)
    elif args.input_file:
        with open(args.input_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
    else:
        input_data = sys.stdin.read()
        urls = parse_input(input_data)

    if not urls:
        print("错误: 未提供有效的 URL", file=sys.stderr)
        sys.exit(1)

    analyzer = PathAnalyzer(min_frequency=args.min_frequency)
    result = analyzer.analyze(urls)

    if args.top > 0:
        result['path_mappings'] = result['path_mappings'][:args.top]

    if args.output == 'json':
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.output == 'simple':
        print(f"\n共 {result['statistics']['total_urls']} 个 URL")
        print(f"发现 {result['statistics']['filtered_paths']} 个二级路径\n")
        for mapping in result['path_mappings']:
            print(f"{mapping['path']:15} {mapping['frequency']:3}次  {mapping['stars']} {mapping['system_type']}")
    else:
        print("\n" + "="*80)
        print("路径分析结果")
        print("="*80)
        print(f"\n总 URL 数: {result['statistics']['total_urls']}")
        print(f"唯一路径: {result['statistics']['unique_paths']}")
        print(f"过滤后路径: {result['statistics']['filtered_paths']}")
        print(f"\n{'路径':<15} {'次数':<6} {'优先级':<6} {'类型':<15}")
        print("-" * 60)
        for mapping in result['path_mappings']:
            print(f"{mapping['path']:<15} {mapping['frequency']:<6} {mapping['priority']:<6} {mapping['stars']} {mapping['system_type']}")


if __name__ == '__main__':
    main()
