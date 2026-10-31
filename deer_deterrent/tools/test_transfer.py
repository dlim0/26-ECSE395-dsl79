import base64
import tempfile
import unittest
from pathlib import Path
from record_photos import fnv1a, save_photo

class PhotoTransferTests(unittest.TestCase):
    def test_known_checksum_vector(self):
        self.assertEqual(fnv1a(b'hello'), '4f9f2cab')

    def test_verified_transfer_preserves_bytes_and_metadata(self):
        payload=b'\xff\xd8transport-test\xff\xd9'
        meta={'frame':7,'state':'CLEAR','jpeg_bytes':len(payload),'fnv1a':fnv1a(payload)}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            name=save_photo(root,meta,[base64.b64encode(payload).decode()], '7')
            self.assertEqual((root/(name+'.jpg')).read_bytes(),payload)
            self.assertTrue((root/(name+'.json')).exists())

    def test_corruption_or_wrong_frame_cannot_be_saved(self):
        payload=b'\xff\xd8transport-test\xff\xd9'
        meta={'frame':7,'state':'CLEAR','jpeg_bytes':len(payload),'fnv1a':fnv1a(payload)}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValueError):
                save_photo(root,meta,[base64.b64encode(payload).decode()], '8')
            corrupted=payload.replace(b'transport',b'Xransport')
            with self.assertRaises(ValueError):
                save_photo(root,meta,[base64.b64encode(corrupted).decode()], '7')
            self.assertEqual(list(root.iterdir()),[])

if __name__=='__main__': unittest.main()
