"""
API 連接測試工具
驗證您的 OpenAI 兼容 API 是否正常工作
"""

import requests
import yaml
import sys
from pathlib import Path
from datetime import datetime


def test_api_connection(endpoint: str, api_key: str, model: str) -> dict:
    """
    測試 API 連接
    
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
    
    # 測試消息
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
        "success": False,
        "endpoint": endpoint,
        "model": model,
        "status_code": None,
        "response_time": None,
        "error": None,
        "sample_response": None
    }
    
    try:
        start_time = datetime.now()
        response = requests.post(
            url,
            json=test_payload,
            headers=headers,
            timeout=30,
            verify=True
        )
        end_time = datetime.now()
        
        result["status_code"] = response.status_code
        result["response_time"] = (end_time - start_time).total_seconds()
        
        if response.status_code == 200:
            response_data = response.json()
            
            if "choices" in response_data and len(response_data["choices"]) > 0:
                message = response_data["choices"][0]["message"]["content"]
                
                if "Hello, API Test Passed!" in message:
                    result["success"] = True
                    result["sample_response"] = message
                    result["message"] = "API 連接測試通過！"
                else:
                    result["error"] = f"響應內容不符合預期: {message}"
            else:
                result["error"] = "響應格式不正確: 缺少 'choices' 字段"
        elif response.status_code == 401:
            result["error"] = "API Key 無效或過期。請檢查 API Key 是否正確。"
        elif response.status_code == 403:
            result["error"] = "API Key 被拒絕。可能沒有權限或配額不足。"
        elif response.status_code == 404:
            result["error"] = "API 端點不存在。請檢查 URL 是否正確。"
        elif response.status_code == 500:
            result["error"] = "API 服務器內部錯誤。請稍後重試。"
        else:
            result["error"] = f"HTTP {response.status_code}: {response.text}"
            
    except requests.exceptions.ConnectionError:
        result["error"] = "無法連接到 API 服務器。請檢查:\n" \
                         "1. 網絡連接是否正常\n" \
                         "2. API 端點 URL 是否正確\n" \
                         "3. 如果是本地 API，服務是否已啟動"
    except requests.exceptions.Timeout:
        result["error"] = "API 請求超時。請檢查:\n" \
                         "1. 網絡連接速度\n" \
                         "2. API 服務器響應時間"
    except Exception as e:
        result["error"] = f"測試失敗: {str(e)}"
    
    return result


def main():
    """主函數"""
    print("=" * 60)
    print("  AI File Repair - API 連接測試工具")
    print("=" * 60)
    print()
    
    # 讀取配置
    config_path = Path.home() / ".hermes" / "config" / "ai-repair-config.yaml"
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            endpoint = config.get('openai_api', {}).get('endpoint', '')
            api_key = config.get('openai_api', {}).get('api_key', '')
            model = config.get('openai_api', {}).get('model', 'gpt-4o-mini')
    else:
        print("⚠️  未找到配置文件，使用預設值")
        endpoint = "https://api.openai.com/v1"
        api_key = input("請輸入 API Key: ")
        model = "gpt-4o-mini"
    
    print(f"_ENDPOINT: {endpoint}")
    print(f"MODEL: {model}")
    print(f"API_KEY: {api_key[:20]}... (顯示前20位)")
    print()
    
    # 測試連接
    print("🔍 正在測試 API 連接...")
    print()
    
    result = test_api_connection(endpoint, api_key, model)
    
    # 顯示結果
    print("=" * 60)
    print("  測試結果")
    print("=" * 60)
    
    if result["success"]:
        print(f"✅ {result['message']}")
        print()
        print(f"📊 連接統計:")
        print(f"   • 響應時間: {result['response_time']:.2f} 秒")
        print(f"   • 模型: {result['model']}")
        print()
        print(f"💡 範例回應:")
        print(f"   {result['sample_response']}")
    else:
        print(f"❌ 測試失敗")
        print()
        print(f"錯誤信息:")
        print(f"   {result['error']}")
    
    print()
    print("=" * 60)
    
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())