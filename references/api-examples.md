---
name: ai-file-repair-api-examples
title: AI Repair API Examples
category: software-development
version: 1.0
---

# API 端點範例 - 支持任意 OpenAI 兼容 API

## 📚 概述

本模組支持**任意 OpenAI API 兼容端點**，無需限定於特定的 AI 服務提供商。

---

## 🔧 支持的 API 端點格式

### 通用格式

```
https://api.example.com/v1
http://localhost:8080/v1
https://your-enterprise-ai.com/api/v1
```

### 端點要求

| 要求 | 說明 | 狀態 |
|------|------|------|
| ✅ POST `/v1/chat/completions` | 傳統 OpenAI 格式 | 支持 |
| ✅ POST `/v1/completions` | legacy completions | 支持 |
| ✅ `Authorization: Bearer` | API Key 認證 | 支持 |
| ✅ JSON 請求體 | standard format | 支持 |
| ✅ JSON 響應體 | standard format | 支持 |

---

## 📋 不同 API 服務配置範例

### 1. OpenAI 官方 API

```yaml
openai_api:
  endpoint: "https://api.openai.com/v1"
  api_key: "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
  model: "gpt-4o-mini"
  timeout: 30
  max_retries: 3
  verify_ssl: true
```

---

### 2. Local AI (Ollama)

```yaml
openai_api:
  endpoint: "http://localhost:11434/v1"
  api_key: "ollama"  # Ollama 通常不需要真實的 API key
  model: "deepseek-r1:1.5b"
  timeout: 60
  max_retries: 3
  verify_ssl: false
```

**使用 Ollama 的優點：**
- ✅ 完全離線，無需網絡
- ✅ 無 API 成本
- ✅ 支持本地模型
- ⚠️ 需要先啟動 Ollama 服務

---

### 3. Local AI (LM Studio)

```yaml
openai_api:
  endpoint: "http://localhost:1234/v1"
  api_key: "lm-studio"
  model: "your-loaded-model"
  timeout: 30
  max_retries: 3
  verify_ssl: false
```

---

### 4. Enterprise AI Platform

```yaml
openai_api:
  endpoint: "https://ai.yourcompany.com/v1"
  api_key: "your-enterprise-key"
  model: "enterprise-gpt-4"
  timeout: 120
  max_retries: 5
  verify_ssl: true
```

---

### 5. 自定義 AI 服務

```yaml
openai_api:
  endpoint: "http://xxx.xx:xxxx/v1"
  api_key: "your-api-key"
  model: "custom-model"
  timeout: 30
  max_retries: 3
  verify_ssl: false
```

---

## 🧪 API 兼容性測試

### 測試腳本

```python
"""
API 兼容性測試工具
驗證您的 API 端點是否兼容
"""

import requests
import json


def test_api_compatibility(endpoint: str, api_key: str, model: str) -> dict:
    """
    測試 API 端點兼容性
    
    Args:
        endpoint: API 端點 URL
        api_key: API Key
        model: 模型名稱
        
    Returns:
        包含測試結果的字典
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    test_payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "Say 'Hello, API Test Passed!' and nothing else."
            }
        ],
        "temperature": 0.3,
        "max_tokens": 50
    }
    
    url = f"{endpoint.rstrip('/')}/chat/completions"
    
    result = {
        "compatible": False,
        "endpoint": endpoint,
        "model": model,
        "status_code": None,
        "response_time": None,
        "error": None
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            url,
            json=test_payload,
            headers=headers,
            timeout=30,
            verify=False  # For testing, disable SSL verification
        )
        end_time = time.time()
        
        result["status_code"] = response.status_code
        result["response_time"] = round(end_time - start_time, 2)
        
        if response.status_code == 200:
            response_data = response.json()
            
            # 檢查響應格式
            if "choices" in response_data and len(response_data["choices"]) > 0:
                message = response_data["choices"][0]["message"]["content"]
                
                # 檢查內容是否符合預期
                if "Hello, API Test Passed!" in message:
                    result["compatible"] = True
                    result["sample_response"] = message
                else:
                    result["error"] = "Response content doesn't match expected format"
            else:
                result["error"] = "Missing 'choices' in response"
        else:
            result["error"] = f"HTTP {response.status_code}: {response.text}"
            
    except requests.RequestException as e:
        result["error"] = f"Request failed: {str(e)}"
    
    return result


# 使用範例
if __name__ == "__main__":
    import time
    
    # 測試不同的 API 端點
    test_configs = [
        {
            "name": "OpenAI",
            "endpoint": "https://api.openai.com/v1",
            "api_key": "sk-...",
            "model": "gpt-4o-mini"
        },
        {
            "name": "Ollama",
            "endpoint": "http://localhost:11434/v1",
            "api_key": "ollama",
            "model": "deepseek-r1:1.5b"
        },
        {
            "name": "Custom",
            "endpoint": "http://xxx.xx:xxxx/v1",
            "api_key": "your-key",
            "model": "your-model"
        }
    ]
    
    for config in test_configs:
        print(f"\n{'='*60}")
        print(f"測試: {config['name']}")
        print(f"端點: {config['endpoint']}")
        print(f"{'='*60}")
        
        result = test_api_compatibility(
            config['endpoint'],
            config['api_key'],
            config['model']
        )
        
        print(f"兼容性: {'✅ 是' if result['compatible'] else '❌ 否'}")
        print(f"狀態碼: {result['status_code']}")
        print(f"響應時間: {result['response_time']} 秒")
        
        if result['error']:
            print(f"錯誤: {result['error']}")
        if result.get('sample_response'):
            print(f"範例回應: {result['sample_response']}")