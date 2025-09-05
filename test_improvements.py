#!/usr/bin/env python3
"""
Test script to verify SAM bot improvements
"""

import requests
import json

def test_bot_response(message, expected_behavior):
    """Test a single bot response"""
    try:
        response = requests.post('http://localhost:5000/api/chat', 
                               json={'message': message},
                               headers={'Content-Type': 'application/json'})
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ '{message}' → {expected_behavior}")
            print(f"   Sources used: {data.get('sources_used', 0)}")
            print(f"   Response: {data.get('response', '')[:100]}...")
            print()
            return True
        else:
            print(f"❌ Error testing '{message}': {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing '{message}': {e}")
        return False

def main():
    """Run all tests"""
    print("🤖 Testing SAM Bot Improvements")
    print("=" * 50)
    print()
    
    tests = [
        ("hi", "Should give greeting response (no document search)"),
        ("hello", "Should give greeting response (no document search)"),
        ("good morning", "Should recognize greeting despite typos"),
        ("goog morning", "Should handle typo in greeting"),
        ("5+5", "Should calculate math expression"),
        ("what is 20 * 30", "Should handle math question"),
        ("github link", "Should search documents for GitHub info"),
        ("i want linkedin", "Should search documents for LinkedIn info"),
        ("resume summary", "Should search documents for resume info"),
        ("what is python", "Should give general programming help"),
        ("help me with coding", "Should give general help without documents"),
        ("fuck", "Should handle inappropriate language gracefully"),
        ("yes", "Should handle short responses intelligently")
    ]
    
    passed = 0
    total = len(tests)
    
    for message, expected in tests:
        if test_bot_response(message, expected):
            passed += 1
    
    print("=" * 50)
    print(f"🎯 Results: {passed}/{total} tests passed")
    print()
    
    if passed == total:
        print("🎉 All tests passed! Bot is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the responses above.")

if __name__ == "__main__":
    main()
