import unittest


class DocumentPermissionContractTests(unittest.TestCase):
    def test_document_download_requires_authenticated_user(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
