from flask import Flask
import os
from flask import request, jsonify
import aiohttp
import asyncio
import logging
from urllib.parse import parse_qs, urlparse, urlencode
import requests

app = Flask(__name__)

# TeraBox cookies dari script pertama
COOKIE = "ndus=YumlKL1peHuism-iCeHS93vJnjxNw_XN_ZFrm5VB"  # add your own cookies

# Headers dari script pertama
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Connection": "keep-alive",
    "DNT": "1",
    "Host": "www.terabox.app",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
    "sec-ch-ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cookie": COOKIE,
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# DL_HEADERS dari script pertama untuk download
DL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;"
              "q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.terabox.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cookie": COOKIE,
}

def get_size(bytes_len: int) -> str:
    """Format file size dari script pertama"""
    if bytes_len >= 1024 ** 3:
        return f"{bytes_len / 1024**3:.2f} GB"
    if bytes_len >= 1024 ** 2:
        return f"{bytes_len / 1024**2:.2f} MB"
    if bytes_len >= 1024:
        return f"{bytes_len / 1024:.2f} KB"
    return f"{bytes_len} bytes"

def find_between(text: str, start: str, end: str) -> str:
    """Find between function dari script pertama"""
    try:
        return text.split(start, 1)[1].split(end, 1)[0]
    except Exception:
        return ""

def get_file_info(share_url: str) -> dict:
    """Get file info function dari script pertama dengan sedikit modifikasi"""
    resp = requests.get(share_url, headers=HEADERS, allow_redirects=True)
    if resp.status_code != 200:
        raise ValueError(f"Failed to fetch share page ({resp.status_code})")
    final_url = resp.url

    parsed = urlparse(final_url)
    surl = parse_qs(parsed.query).get("surl", [None])[0]
    if not surl:
        raise ValueError("Invalid share URL (missing surl)")

    page = requests.get(final_url, headers=HEADERS)
    html = page.text

    js_token = find_between(html, 'fn%28%22', '%22%29')
    logid = find_between(html, 'dp-logid=', '&')
    bdstoken = find_between(html, 'bdstoken":"', '"')
    if not all([js_token, logid, bdstoken]):
        raise ValueError("Failed to extract authentication tokens")

    params = {
        "app_id": "250528", "web": "1", "channel": "dubox",
        "clienttype": "0", "jsToken": js_token, "dp-logid": logid,
        "page": "1", "num": "20", "by": "name", "order": "asc",
        "site_referer": final_url, "shorturl": surl, "root": "1,",
    }
    info = requests.get(
        "https://www.terabox.app/share/list?" + urlencode(params),
        headers=HEADERS
    ).json()

    if info.get("errno") or not info.get("list"):
        errmsg = info.get("errmsg", "Unknown error")
        raise ValueError(f"List API error: {errmsg}")

    return info["list"]  # Return all files

def extract_thumbnail_dimensions(url: str) -> str:
    """Extract dimensions from thumbnail URL's size parameter"""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    size_param = params.get('size', [''])[0]
    
    # Extract numbers from size format like c360_u270
    if size_param:
        parts = size_param.replace('c', '').split('_u')
        if len(parts) == 2:
            return f"{parts[0]}x{parts[1]}"
    return "original"

def format_message(file_data):
    """Format message function dengan DL_HEADERS mechanism"""
    # Process thumbnails
    thumbnails = {}
    if 'thumbs' in file_data:
        for key, url in file_data['thumbs'].items():
            if url:  # Skip empty URLs
                dimensions = extract_thumbnail_dimensions(url)
                thumbnails[dimensions] = url

    file_name = file_data["server_filename"]
    size_bytes = int(file_data.get("size", 0))
    file_size = get_size(size_bytes)
    download_link = file_data["dlink"]
    
    # Test download link dengan DL_HEADERS
    try:
        test_response = requests.head(download_link, headers=DL_HEADERS, timeout=10)
        download_status = "working" if test_response.status_code == 200 else "redirect_needed"
        final_download_url = test_response.url if hasattr(test_response, 'url') else download_link
    except Exception as e:
        download_status = "error"
        final_download_url = download_link

    sk = {
        'Title': file_name,
        'Size': file_size,
        'Size_Bytes': size_bytes,
        'Direct Download Link': final_download_url,
        'Original_DLink': download_link,
        'Download_Status': download_status,
        'Thumbnails': thumbnails,
        'DL_Headers_Required': True  # Indicator that DL_HEADERS should be used for download
    }
    return sk

@app.route('/')
def hello_world():
    response = {'status': 'success', 'message': 'Working Fully with DL_HEADERS', 'Contact': '@GuyXD'}
    return response

@app.route(rule='/api', methods=['GET'])
def Api():
    try:
        url = request.args.get('url', 'No URL Provided')
        logging.info(f"Received request for URL: {url}")
        
        # Use the improved get_file_info function from script 1
        file_list = get_file_info(url)
        
        if file_list:
            formatted_message = [format_message(item) for item in file_list]
            logging.info(f"Formatted message: {formatted_message}")
        else:
            formatted_message = None
            
        response = {
            'ShortLink': url, 
            'Extracted Info': formatted_message,
            'status': 'success',
            'download_instructions': {
                'use_headers': DL_HEADERS,
                'note': 'Use DL_HEADERS for actual file download'
            }
        }
        return jsonify(response)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({'status': 'error', 'message': str(e), 'Link': url})

@app.route(rule='/download', methods=['GET'])
def download_file():
    """New endpoint for direct download using DL_HEADERS mechanism"""
    try:
        download_url = request.args.get('url', '')
        if not download_url:
            return jsonify({'status': 'error', 'message': 'No download URL provided'})
        
        # Use DL_HEADERS for download
        response = requests.get(download_url, headers=DL_HEADERS, stream=True)
        
        if response.status_code == 200:
            return jsonify({
                'status': 'success',
                'message': 'Download link is working',
                'headers_used': DL_HEADERS,
                'final_url': response.url
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': f'Download failed with status: {response.status_code}',
                'headers_used': DL_HEADERS
            })
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route(rule='/help', methods=['GET'])
def help():
    try:
        response = {
            'Info': "Updated API with DL_HEADERS mechanism from script 1",
            'Example': 'https://teraboxx.vercel.app/api?url=https://terafileshare.com/s/1_1SzMvaPkqZ-yWokFCrKyA',
            'Download_Test': 'https://teraboxx.vercel.app/download?url=DIRECT_DOWNLOAD_LINK',
            'Headers_Info': {
                'DL_HEADERS': DL_HEADERS,
                'Note': 'Use these headers for downloading files'
            }
        }
        return jsonify(response)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        response = {
            'Info': "Updated API with DL_HEADERS mechanism from script 1",
            'Example': 'https://teraboxx.vercel.app/api?url=https://terafileshare.com/s/1_1SzMvaPkqZ-yWokFCrKyA',
            'Error': str(e)
        }
        return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
