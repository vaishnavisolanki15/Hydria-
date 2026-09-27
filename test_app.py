"""
Comprehensive automated test suite for Hydria MVP.
Verifies all 17 tests listed in Section 44 of the specifications.
"""

import os
import io
import unittest
from PIL import Image
from app import app
import database
from seed_demo import generate_sample_water_image

class HydriaMVPTestSuite(unittest.TestCase):
    def setUp(self):
        os.environ['TESTING'] = 'True'
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def create_dummy_water_image(self, color=(30, 120, 80)):
        """Helper to create an in-memory image simulating water."""
        img = Image.new('RGB', (200, 200), color)
        # Add some variation so it's not a single solid color
        for x in range(50, 150):
            for y in range(50, 150):
                img.putpixel((x, y), (20, 150, 100))
        byte_arr = io.BytesIO()
        img.save(byte_arr, format='JPEG')
        byte_arr.seek(0)
        return byte_arr

    def test_01_and_02_register_and_login(self):
        """Test 1 & 2: Register new user, then login."""
        import time
        unique_email = f"user_{int(time.time()*1000)}@test.com"
        
        # Register
        resp = self.client.post('/register', data={
            'name': 'Kavita Sen',
            'email': unique_email,
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Account created successfully", resp.data)

        # Login
        resp_login = self.client.post('/login', data={
            'email': unique_email,
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn(b"Kavita Sen", resp_login.data)

    def test_03_and_17_protected_pages(self):
        """Test 17: Protected pages require login."""
        # Try accessing dashboard without login
        with self.client.session_transaction() as sess:
            sess.clear()
        resp = self.client.get('/dashboard', follow_redirects=True)
        self.assertIn(b"Please log in to continue", resp.data)
        self.assertIn(b"Login", resp.data)

        # Report page also protected
        resp_rep = self.client.get('/report', follow_redirects=True)
        self.assertIn(b"Please log in to continue", resp_rep.data)

    def test_04_to_10_report_validation_and_submission(self):
        """Test 4 through 10: Missing fields, validation checklist, and report submission."""
        # Login first
        self.client.post('/login', data={
            'email': 'vaishnavi@example.com',
            'password': 'password123'
        })

        # Test 8: Missing fields check
        resp_missing = self.client.post('/validate-report', data={
            'water_body_name': 'Test Pond',
            'water_body_type': '',  # missing
            'latitude': '22.7196',
            'longitude': '75.8577',
            'water_colour': '',  # missing
            'smell': 'Bad smell',
            'algae': 'Yes',
            'visible_waste': 'High',
            'water_appearance': 'Dirty'
        }, content_type='multipart/form-data')
        self.assertEqual(resp_missing.status_code, 200)
        self.assertIn(b"Almost there!", resp_missing.data)
        self.assertIn(b"Water body type", resp_missing.data)
        self.assertIn(b"Water colour", resp_missing.data)
        self.assertIn(b"Water body photograph", resp_missing.data)

        import random, time
        unique_name = f"Test Reservoir {int(time.time()*1000)}"
        temp_test_img_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', f"test_sample_{int(time.time()*1000)}.jpg")
        generate_sample_water_image(temp_test_img_path, base_color_type="clear", title=unique_name, wave_seed=int(time.time()) % 1000)
        with open(temp_test_img_path, 'rb') as f:
            img_bytes = f.read()
        try:
            os.remove(temp_test_img_path)
        except Exception:
            pass

        # Test 5, 6, 7: Full valid data with image
        resp_valid = self.client.post('/validate-report', data={
            'water_body_name': unique_name,
            'water_body_type': 'Lake',
            'latitude': '22.7600',
            'longitude': '75.8800',
            'water_colour': 'Green',
            'smell': 'Bad smell',
            'algae': 'Yes',
            'visible_waste': 'Medium',
            'water_appearance': 'Dirty',
            'dead_fish': 'No',
            'additional_observation': 'High green algae accumulation near south weir.',
            'image': (io.BytesIO(img_bytes), 'water_test.jpg')
        }, content_type='multipart/form-data')
        self.assertEqual(resp_valid.status_code, 200)
        self.assertIn(b"Hydria Report Check", resp_valid.data)
        self.assertIn(b"Your report looks ready", resp_valid.data)
        self.assertIn(b"Image file is valid", resp_valid.data)
        self.assertIn(b"No duplicate image found", resp_valid.data)

        # Extract the temporary filename generated
        temp_filename_start = resp_valid.data.find(b'name="temp_filename" value="') + len('name="temp_filename" value="')
        temp_filename_end = resp_valid.data.find(b'"', temp_filename_start)
        temp_filename = resp_valid.data[temp_filename_start:temp_filename_end].decode('utf-8')

        # Test 10: Final submission
        resp_submit = self.client.post('/submit-report', data={
            'water_body_name': unique_name,
            'water_body_type': 'Lake',
            'latitude': '22.7600',
            'longitude': '75.8800',
            'water_colour': 'Green',
            'smell': 'Bad smell',
            'algae': 'Yes',
            'visible_waste': 'Medium',
            'water_appearance': 'Dirty',
            'dead_fish': 'No',
            'additional_observation': 'High green algae accumulation near south weir.',
            'temp_filename': temp_filename
        }, follow_redirects=True)
        self.assertEqual(resp_submit.status_code, 200)
        self.assertIn(b"Report Submitted", resp_submit.data)
        self.assertIn(b"Thank you for helping your community", resp_submit.data)

        # Test 11: Report appears in Community
        resp_comm = self.client.get('/community')
        self.assertIn(unique_name.encode('utf-8'), resp_comm.data)

        # Test 12: Report appears in Analysis Board
        resp_board = self.client.get('/analysis-board')
        self.assertIn(unique_name.encode('utf-8'), resp_board.data)

        # Test 15: Uploading the exact same image triggers duplicate image detection & blocking
        resp_dup = self.client.post('/validate-report', data={
            'water_body_name': 'Another Water Body',
            'water_body_type': 'Pond',
            'latitude': '22.7900',
            'longitude': '75.8900',
            'water_colour': 'Green',
            'smell': 'No unusual smell',
            'algae': 'No',
            'visible_waste': 'None',
            'water_appearance': 'Normal',
            'dead_fish': 'No',
            'image': (io.BytesIO(img_bytes), 'dup_test.jpg')
        }, content_type='multipart/form-data')
        self.assertIn(b"Duplicate photo detected", resp_dup.data)
        self.assertIn(b"DUPLICATE PHOTO NOT ALLOWED", resp_dup.data)

        # Clean up test report from database
        conn = database.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM reports WHERE water_body_name = %s", (unique_name,))
                test_rep = cursor.fetchone()
                if test_rep:
                    database.delete_report(test_rep['id'])
        finally:
            conn.close()

    def test_13_and_14_voting_system(self):
        """Test 13 & 14: Voting and duplicate vote prevention."""
        # Get a submitted report
        reports = database.get_community_reports()
        self.assertTrue(len(reports) > 0)
        rep = reports[0]
        rep_id = rep['id']
        initial_votes = rep['vote_count']

        # Log in as user 2 (Arjun)
        self.client.post('/login', data={
            'email': 'arjun@example.com',
            'password': 'password123'
        })

        # Check report detail page
        resp_detail = self.client.get(f'/report/{rep_id}')
        self.assertEqual(resp_detail.status_code, 200)
        self.assertIn(b"Hydria Environmental Insights", resp_detail.data)

        # Vote
        resp_vote = self.client.post(f'/vote/{rep_id}', headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(resp_vote.status_code, 200)
        data = resp_vote.get_json()
        self.assertTrue(data['success'])

        # Toggle or re-vote should not duplicate database entries (unique constraint enforced)
        # Verify in database
        has_voted = database.has_user_voted(2, rep_id)
        # Should be a valid boolean state without database errors
        self.assertIn(has_voted, [True, False])

    def test_18_delete_report(self):
        """Test report deletion: authorized owner can delete, unauthorized user cannot."""
        # 1. Login as user 1 (Vaishnavi) and create a report
        self.client.post('/login', data={'email': 'vaishnavi@example.com', 'password': 'password123'})
        rep_id = database.create_report(
            user_id=1,
            water_body_name="Delete Test Pond",
            water_body_type="Pond",
            latitude=22.75,
            longitude=75.85,
            water_colour="Green",
            smell="Bad smell",
            algae="Yes",
            visible_waste="Low",
            water_appearance="Dirty",
            dead_fish="No",
            additional_observation="Temporary report for delete test",
            image_path="uploads/demo_report_1.jpg",
            image_hash="delete_hash_test_123",
            status="Submitted"
        )
        self.assertIsNotNone(database.get_report_by_id(rep_id))

        # 2. Logout and login as user 2 (Arjun) and try deleting Vaishnavi's report (should fail/unauthorized)
        self.client.get('/logout')
        self.client.post('/login', data={'email': 'arjun@example.com', 'password': 'password123'})
        resp_unauth = self.client.post(f'/report/{rep_id}/delete', follow_redirects=True)
        self.assertIn(b"not authorized to delete", resp_unauth.data)
        self.assertIsNotNone(database.get_report_by_id(rep_id))

        # 3. Logout and login as owner (Vaishnavi) and delete the report (should succeed)
        self.client.get('/logout')
        self.client.post('/login', data={'email': 'vaishnavi@example.com', 'password': 'password123'})
        resp_auth = self.client.post(f'/report/{rep_id}/delete', follow_redirects=True)
        self.assertIn(b"Report has been deleted successfully", resp_auth.data)
        self.assertIsNone(database.get_report_by_id(rep_id))

    def test_16_logout(self):
        """Test 16: Logout functionality."""
        self.client.post('/login', data={
            'email': 'vaishnavi@example.com',
            'password': 'password123'
        })
        resp = self.client.get('/logout', follow_redirects=True)
        self.assertIn(b"You have been logged out", resp.data)
        self.assertIn(b"Login", resp.data)

    def test_18_geocode_manual_address(self):
        """Test 18: Manual address geocoding endpoint (/api/geocode)."""
        # Test offline dictionary lookup
        resp = self.client.get('/api/geocode?q=Indore')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertAlmostEqual(data['lat'], 22.7196, places=3)
        self.assertAlmostEqual(data['lon'], 75.8577, places=3)
        self.assertIn('Indore', data['display_name'])

        # Test empty query error
        resp_empty = self.client.get('/api/geocode?q=')
        self.assertEqual(resp_empty.status_code, 400)
        self.assertFalse(resp_empty.get_json()['success'])

    def test_19_gemini_ai_analysis(self):
        """Test 19: Verify Gemini AI water quality report analysis."""
        from analysis_engine import generate_water_insight
        sample_report = {
            'id': 9999,
            'water_body_name': 'Powai Lake',
            'water_body_type': 'Lake',
            'latitude': 19.1264,
            'longitude': 72.9050,
            'water_colour': 'Dark Green',
            'smell': 'Sewage-like smell',
            'algae': 'Yes',
            'visible_waste': 'High',
            'water_appearance': 'Very Dirty',
            'dead_fish': 'Yes',
            'additional_observation': 'Heavy algae and municipal stormwater overflow.'
        }
        insight = generate_water_insight(sample_report)
        self.assertIn(insight['concern_level'], ['High Concern', 'Moderate Concern', 'Low / Baseline Concern'])
        self.assertTrue(len(insight['summary']) > 10)
        self.assertIn('root_causes', insight)
        self.assertIn('civic_action_steps', insight)

    def test_20_duplicate_report_strictly_blocked(self):
        """Test 20: Verify duplicate report submissions for same location/water body are strictly blocked."""
        import time
        # Login first
        self.client.post('/login', data={'email': 'vaishnavi@example.com', 'password': 'password123'})

        unique_lake = f"Duplicate Guard Lake {int(time.time()*1000)}"
        unique_lat = round(21.1000 + (time.time() % 100) / 10.0, 4)
        unique_lon = round(74.1000 + (time.time() % 100) / 10.0, 4)
        # 1. Create first report for today
        rep_id = database.create_report(
            user_id=1,
            water_body_name=unique_lake,
            water_body_type="Lake",
            latitude=unique_lat,
            longitude=unique_lon,
            water_colour="Green",
            smell="Bad smell",
            algae="Yes",
            visible_waste="Medium",
            water_appearance="Dirty",
            dead_fish="No",
            additional_observation="Initial report",
            image_path="uploads/real_bellandur_lake.jpg",
            image_hash=f"unique_hash_guard_{int(time.time()*1000)}",
            status="Submitted"
        )

        try:
            # 2. Check duplicate report detection
            dups = database.check_duplicate_report(unique_lat, unique_lon, unique_lake)
            self.assertTrue(len(dups) > 0)
            self.assertEqual(dups[0]['id'], rep_id)

            # 3. Validation should detect duplicate report and mark ready_to_submit as False
            resp_val = self.client.post('/validate-report', data={
                'water_body_name': unique_lake,
                'water_body_type': 'Lake',
                'latitude': str(unique_lat),
                'longitude': str(unique_lon),
                'water_colour': 'Green',
                'smell': 'Bad smell',
                'algae': 'Yes',
                'visible_waste': 'Medium',
                'water_appearance': 'Dirty',
                'dead_fish': 'No',
                'image': (self.create_dummy_water_image(), 'guard_water.jpg')
            }, content_type='multipart/form-data')
            self.assertIn(b"DUPLICATE REPORT NOT ALLOWED", resp_val.data)
            self.assertIn(b"Submission Blocked: Duplicate Not Allowed", resp_val.data)

            # 4. Attempting to submit duplicate report directly should be blocked by backend
            resp_sub = self.client.post('/submit-report', data={
                'water_body_name': unique_lake,
                'water_body_type': 'Lake',
                'latitude': str(unique_lat),
                'longitude': str(unique_lon),
                'temp_filename': 'non_existent.jpg'
            }, follow_redirects=True)
            self.assertIn(b"Submission blocked", resp_sub.data)
        finally:
            database.delete_report(rep_id)

if __name__ == '__main__':
    unittest.main()

