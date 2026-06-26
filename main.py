from flask import Flask, request, jsonify
from flask_cors import CORS
import requests, os, base64

app = Flask(__name__)
CORS(app, origins='*')

GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent'

def call_gemini(payload, api_key):
    r = requests.post(
        GEMINI_URL,
        headers={'x-goog-api-key': api_key, 'Content-Type': 'application/json'},
        json=payload,
        timeout=30
    )
    return r

@app.route('/analyze', methods=['POST'])
def analyze():
    """接收商品截圖 + 分潤連結，回傳辨識結果"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'success': False, 'error': 'API key not configured'}), 500

    data = request.get_json()
    image_b64 = data.get('image', '')
    image_type = data.get('image_type', 'image/jpeg')
    link = data.get('link', '')

    if not image_b64:
        return jsonify({'success': False, 'error': '請上傳商品截圖'}), 400

    prompt = f"""請分析這張蝦皮商品截圖，提取以下資訊並用 JSON 格式回答（只輸出 JSON，不要其他文字）：
{{
  "name": "商品名稱",
  "price": "價格（含原價/折扣價）",
  "category": "商品分類（服飾/美妝/電子/居家/食品/其他）",
  "key_features": ["特點1", "特點2", "特點3"],
  "selling_points": ["賣點1", "賣點2"],
  "target_audience": "目標受眾描述"
}}"""

    try:
        r = call_gemini({
            'contents': [{'parts': [
                {'inline_data': {'mime_type': image_type, 'data': image_b64}},
                {'text': prompt}
            ]}],
            'generationConfig': {'maxOutputTokens': 500, 'temperature': 0.1,
                               'thinkingConfig': {'thinkingBudget': 0}}
        }, api_key)

        if r.status_code != 200:
            return jsonify({'success': False, 'error': f'Gemini 錯誤 {r.status_code}: {r.text[:200]}'}), 500

        text = r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        if '```' in text:
            text = text.split('```')[1]
            if text.startswith('json'): text = text[4:]

        import json
        product_data = json.loads(text.strip())
        product_data['link'] = link
        return jsonify({'success': True, 'product': product_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:100]}), 500


@app.route('/generate', methods=['POST'])
def generate():
    """根據商品資料 + 風格生成文案"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'success': False, 'error': 'API key not configured'}), 500

    data = request.get_json()
    product = data.get('product', {})
    style = data.get('style', 'casual')  # casual/hype/review/story
    count = data.get('count', 3)  # 生成幾則

    style_desc = {
        'casual': '閒聊推薦風，像朋友分享好物，自然親切，適當使用 emoji',
        'hype': '限時優惠感，製造急迫感和搶購氛圍，強調折扣和促銷',
        'review': '開箱心得風，像真實使用者分享，有個人感受和評價',
        'story': '說故事風，從生活情境出發引出商品，有代入感'
    }.get(style, '閒聊推薦風')

    link = product.get('link', '')
    link_text = f'\n\n🔗 購買連結：{link}' if link else ''

    prompt = f"""你是一位台灣 Threads 社群達人，擅長寫蝦皮商品推廣文案。

商品資訊：
- 名稱：{product.get('name', '未知商品')}
- 價格：{product.get('price', '詳見連結')}
- 分類：{product.get('category', '')}
- 特點：{', '.join(product.get('key_features', []))}
- 賣點：{', '.join(product.get('selling_points', []))}
- 目標受眾：{product.get('target_audience', '')}

寫作風格：{style_desc}

請生成 {count} 則不同的 Threads 貼文文案，每則約 100-200 字。
格式要求：
- 適合 Threads 平台的口語化台灣繁體中文
- 自然使用 emoji（不要過多）
- 每則風格略有不同
- 結尾加上 #蝦皮購物 #好物推薦 和 1-2 個相關 hashtag
- 每則文案最後加上「{link_text.strip()}」（如果有連結）

請用以下格式輸出：
【文案1】
（內容）

【文案2】
（內容）

【文案3】
（內容）"""

    try:
        r = call_gemini({
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'maxOutputTokens': 2000, 'temperature': 0.8,
                               'thinkingConfig': {'thinkingBudget': 0}}
        }, api_key)

        if r.status_code != 200:
            return jsonify({'success': False, 'error': f'Gemini 錯誤 {r.status_code}: {r.text[:200]}'}), 500

        text = r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        return jsonify({'success': True, 'result': text})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:100]}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')
