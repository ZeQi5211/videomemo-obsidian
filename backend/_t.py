# -*- coding: utf-8 -*-
import sys, io, unittest
sys.path.insert(0, r'I:\70_applist\videomemo\backend')
buf = io.StringIO()
runner = unittest.TextTestRunner(stream=buf, verbosity=1)
suite = unittest.defaultTestLoader.discover(r'I:\70_applist\videomemo\backend\tests', pattern='test_note_helper.py')
r = runner.run(suite)
with open(r'I:\70_applist\videomemo\backend\_test_out.txt', 'w', encoding='utf-8') as f:
    f.write(buf.getvalue())
sys.exit(0 if r.wasSuccessful() else 1)
