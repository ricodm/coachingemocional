#!/usr/bin/env python3
"""
Password Reset Integration Test
Tests the complete forgot password flow including token generation and validation
"""

import asyncio
import requests
import sys
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv('backend/.env')

class PasswordResetIntegrationTest:
    def __init__(self):
        self.base_url = "https://71832b61-f09e-4b43-b8fe-dcfd4ba45e0d.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.test_email = f"reset_test_{datetime.now().strftime('%H%M%S')}@test.com"
        self.user_id = None
        self.reset_token = None
        
    async def setup_test_user(self):
        """Create a test user for password reset testing"""
        print("🔧 Setting up test user...")
        
        user_data = {
            "email": self.test_email,
            "name": "Reset Test User",
            "phone": "11999888777",
            "password": "oldpassword123"
        }
        
        response = requests.post(f"{self.api_url}/auth/register", json=user_data)
        if response.status_code == 200:
            data = response.json()
            self.user_id = data['user']['id']
            print(f"✅ Test user created: {self.test_email}")
            return True
        else:
            print(f"❌ Failed to create test user: {response.text}")
            return False
    
    async def test_forgot_password_and_get_token(self):
        """Test forgot password and retrieve the generated token from database"""
        print("🔍 Testing forgot password and token generation...")
        
        # Request password reset
        forgot_data = {"email": self.test_email}
        response = requests.post(f"{self.api_url}/auth/forgot-password", json=forgot_data)
        
        if response.status_code != 200:
            print(f"❌ Forgot password request failed: {response.text}")
            return False
        
        # Get the token from database
        client = AsyncIOMotorClient(os.environ['MONGO_URL'])
        db = client[os.environ['DB_NAME']]
        
        # Find the most recent token for our user
        token_doc = await db.password_reset_tokens.find_one(
            {"user_id": self.user_id, "used": False},
            sort=[("created_at", -1)]
        )
        
        client.close()
        
        if token_doc:
            self.reset_token = token_doc['token']
            print(f"✅ Password reset token generated and stored in database")
            print(f"   Token expires at: {token_doc['expires_at']}")
            return True
        else:
            print("❌ No reset token found in database")
            return False
    
    def test_reset_password_with_valid_token(self):
        """Test password reset with the valid token"""
        print("🔍 Testing password reset with valid token...")
        
        if not self.reset_token:
            print("❌ No reset token available")
            return False
        
        reset_data = {
            "token": self.reset_token,
            "new_password": "newpassword123"
        }
        
        response = requests.post(f"{self.api_url}/auth/reset-password", json=reset_data)
        
        if response.status_code == 200:
            data = response.json()
            expected_message = "Senha redefinida com sucesso"
            if expected_message in data.get('message', ''):
                print("✅ Password reset successful")
                return True
            else:
                print(f"❌ Unexpected success message: {data.get('message')}")
                return False
        else:
            print(f"❌ Password reset failed: {response.text}")
            return False
    
    def test_login_with_new_password(self):
        """Test login with the new password"""
        print("🔍 Testing login with new password...")
        
        login_data = {
            "email": self.test_email,
            "password": "newpassword123"
        }
        
        response = requests.post(f"{self.api_url}/auth/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('token') and data.get('user'):
                print("✅ Login successful with new password")
                return True
            else:
                print("❌ Login response missing token or user data")
                return False
        else:
            print(f"❌ Login failed with new password: {response.text}")
            return False
    
    def test_login_with_old_password(self):
        """Test that old password no longer works"""
        print("🔍 Testing that old password no longer works...")
        
        login_data = {
            "email": self.test_email,
            "password": "oldpassword123"
        }
        
        response = requests.post(f"{self.api_url}/auth/login", json=login_data)
        
        if response.status_code == 401:
            print("✅ Old password correctly rejected")
            return True
        else:
            print(f"❌ Old password should have been rejected but got: {response.status_code}")
            return False
    
    async def test_token_marked_as_used(self):
        """Test that the token is marked as used in database"""
        print("🔍 Testing that token is marked as used...")
        
        client = AsyncIOMotorClient(os.environ['MONGO_URL'])
        db = client[os.environ['DB_NAME']]
        
        token_doc = await db.password_reset_tokens.find_one({"token": self.reset_token})
        client.close()
        
        if token_doc and token_doc.get('used') == True:
            print("✅ Token correctly marked as used in database")
            return True
        else:
            print("❌ Token not marked as used in database")
            return False
    
    def test_reuse_token(self):
        """Test that used token cannot be reused"""
        print("🔍 Testing that used token cannot be reused...")
        
        reset_data = {
            "token": self.reset_token,
            "new_password": "anothernewpassword123"
        }
        
        response = requests.post(f"{self.api_url}/auth/reset-password", json=reset_data)
        
        if response.status_code == 400:
            data = response.json()
            if "Token inválido ou expirado" in data.get('detail', ''):
                print("✅ Used token correctly rejected")
                return True
            else:
                print(f"❌ Unexpected error message: {data.get('detail')}")
                return False
        else:
            print(f"❌ Used token should have been rejected but got: {response.status_code}")
            return False
    
    async def run_integration_test(self):
        """Run the complete integration test"""
        print("🚀 Starting Password Reset Integration Test")
        print("=" * 60)
        
        tests_passed = 0
        total_tests = 7
        
        # Run tests in sequence
        if await self.setup_test_user():
            tests_passed += 1
        
        if await self.test_forgot_password_and_get_token():
            tests_passed += 1
        
        if self.test_reset_password_with_valid_token():
            tests_passed += 1
        
        if self.test_login_with_new_password():
            tests_passed += 1
        
        if self.test_login_with_old_password():
            tests_passed += 1
        
        if await self.test_token_marked_as_used():
            tests_passed += 1
        
        if self.test_reuse_token():
            tests_passed += 1
        
        print("\n" + "=" * 60)
        print("📊 INTEGRATION TEST SUMMARY")
        print(f"✅ Passed: {tests_passed}/{total_tests}")
        print(f"❌ Failed: {total_tests - tests_passed}/{total_tests}")
        
        if tests_passed == total_tests:
            print("🎉 All integration tests passed! Password reset flow is working correctly.")
            return True
        else:
            print("⚠️  Some integration tests failed.")
            return False

async def main():
    tester = PasswordResetIntegrationTest()
    success = await tester.run_integration_test()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))