"""PIC0000 metadata parser tests without copying commercial image payloads."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pic0000_catalog import catalog_chunks, MAGIC

def record(format_marker=15,width=32,height=64,flags=0,allocated=48):
    assert allocated>=32 and allocated%16==0
    return (
        MAGIC + flags.to_bytes(4,"big") + bytes([format_marker]) +
        width.to_bytes(2,"big") + height.to_bytes(2,"big") +
        bytes(allocated-17)
    )

class Pic0000CatalogTests(unittest.TestCase):
    def test_multiple_header_flags_and_images(self):
        data=(record(15,32,64,0,48)+record(8,64,32,0x4000,64)+
              record(16,32,64,0,32))
        chunks=catalog_chunks(data)
        self.assertEqual(len(chunks),3)
        self.assertEqual([c.local_file_offset for c in chunks],[0,48,112])
        self.assertEqual([c.format_marker for c in chunks],[15,8,16])
        self.assertEqual([c.header_flags for c in chunks],[0,0x4000,0])
        self.assertEqual([(c.width,c.height) for c in chunks],
                         [(32,64),(64,32),(32,64)])
        self.assertEqual([c.allocated_bytes for c in chunks],[48,64,32])
        self.assertTrue(all(len(c.sha256)==64 for c in chunks))

    def test_unaligned_signature_rejected(self):
        data=record()+b"x"+record()
        with self.assertRaisesRegex(ValueError,"unaligned"):
            catalog_chunks(data)

    def test_corrupt_flags_format_and_dimensions_rejected(self):
        for broken in (record(flags=0x4001),
                       record(format_marker=13),
                       record(width=0),
                       record(height=0),
                       record(width=4097)):
            with self.subTest(broken=broken[:24].hex()):
                with self.assertRaises(ValueError):
                    catalog_chunks(broken)

    def test_no_raw_image_export(self):
        data=record(4,32,32)
        parsed=catalog_chunks(data)[0]
        self.assertFalse(hasattr(parsed,"image_bytes"))
        self.assertFalse(hasattr(parsed,"pixels"))

if __name__=="__main__":
    unittest.main()
