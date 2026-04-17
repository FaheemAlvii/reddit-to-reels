import requests
import json

# Test Streamlabs Polly API with POST
url = 'https://streamlabs.com/polly/speak'
data = {
    'text': 'Hello, this is a test of the Brian voice.',
    'voice': 'Brian'
}
headers = {
    'referer': 'https://streamlabs.com',
    'User-Agent': 'Mozilla/5.0'
}

print("Testing Streamlabs Polly API...")
response = requests.post(url, data=data, headers=headers, timeout=10)

print(f"Status Code: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}")

# Parse JSON
result = response.json()
print(f"JSON Response: {result}")

if result.get('success'):
    speak_url = result.get('speak_url')
    print(f"\n✓ Got speak_url: {speak_url}")
    
    # Download audio
    audio_response = requests.get(speak_url, timeout=10)
    print(f"Audio Status: {audio_response.status_code}")
    print(f"Audio Length: {len(audio_response.content)} bytes")
    print(f"First 10 bytes: {' '.join(f'{b:02x}' for b in audio_response.content[:10])}")
    
    # Save
    with open('test_tts.mp3', 'wb') as f:
        f.write(audio_response.content)
    print("✅ Saved to test_tts.mp3")
else:
    print("❌ API returned success=false")
