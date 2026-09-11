from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

# Fix the profile API typo caught during source review.
backend = ROOT / 'backend/api/mobile_social_v31.php'
text = backend.read_text(encoding='utf-8')
text = text.replace(
    "$userUpdate['experience_yrs']=max(0,min(60,(int)$_POST['experience']);",
    "$userUpdate['experience_yrs']=max(0,min(60,(int)$_POST['experience']));",
)
backend.write_text(text, encoding='utf-8')

# Keep the deploy companion beside the Flutter project as with mobile.php.
flutter_backend = ROOT / 'flutter/backend/api/mobile_social_v31.php'
flutter_backend.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(backend, flutter_backend)

# Remove the final v3.0 analyzer warning from the security screen.
security = ROOT / 'flutter/lib/screens/security_screen.dart'
text = security.read_text(encoding='utf-8')
text = text.replace("\n  int _int(dynamic value) => value is int ? value : int.tryParse('$value') ?? 0;\n", "\n")
security.write_text(text, encoding='utf-8')

# Final parity release version.
pubspec = ROOT / 'flutter/pubspec.yaml'
text = pubspec.read_text(encoding='utf-8')
import re
text = re.sub(r'^version:\s*[^\n]+', 'version: 3.1.0+310', text, count=1, flags=re.M)
pubspec.write_text(text, encoding='utf-8')

# Release notes describe only functionality actually present in committed code.
(ROOT / 'flutter/V3.1.md').write_text('''# TaleemPK Flutter v3.1\n\n## Native parity\n- Profile: cover/avatar editing, bio/headline, education and teacher details, followers/following, public profiles, follow/block/report, verified credentials, Posts/Uploads/Answers/Badges tabs.\n- Feed: Latest/Following/Questions/Unsolved tabs, subject filters, cursor paging, media/file posts, public/followers visibility, anonymous questions, likes/dislikes, comments, save, repost, share, edit/delete/report.\n- Verification: student/teacher/institute application, CNIC/B-Form validation, identity and role documents, status timeline, requested-info resubmission and withdrawal.\n\n## Performance\n- Feed uses cursor paging rather than OFFSET.\n- Media, viewer reactions, saves and repost state are batched per page.\n- Profile data has a short native memory cache and images use the shared cached-network-image layer.\n- Existing chat outbox, short-poll overlap protection and cached media remain enabled.\n\n## Deployment\nDeploy both `backend/api/mobile.php` and `backend/api/mobile_social_v31.php` to the website `api/` directory before testing this APK.\n''', encoding='utf-8')
