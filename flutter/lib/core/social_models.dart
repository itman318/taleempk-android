class SocialMedia {
  const SocialMedia({
    required this.id,
    required this.url,
    required this.type,
    required this.name,
  });
  final int id;
  final String url, type, name;

  bool get isImage {
    final t = type.toLowerCase();
    final n = name.toLowerCase();
    return const ['jpg', 'jpeg', 'png', 'webp', 'gif'].contains(t) ||
        n.endsWith('.jpg') ||
        n.endsWith('.jpeg') ||
        n.endsWith('.png') ||
        n.endsWith('.webp') ||
        n.endsWith('.gif');
  }

  factory SocialMedia.fromJson(Map<String, dynamic> j) => SocialMedia(
        id: smInt(j['id']),
        url: '${j['url'] ?? ''}',
        type: '${j['type'] ?? 'file'}',
        name: '${j['name'] ?? ''}',
      );
}

class SocialSourcePost {
  const SocialSourcePost({
    required this.id,
    required this.author,
    required this.username,
    required this.content,
    required this.subject,
    required this.type,
    required this.createdAt,
  });
  final int id;
  final String author, username, content, subject, type, createdAt;

  factory SocialSourcePost.fromJson(Map<String, dynamic> j) => SocialSourcePost(
        id: smInt(j['id']),
        author: '${j['author'] ?? ''}',
        username: '${j['username'] ?? ''}',
        content: '${j['content'] ?? ''}',
        subject: '${j['subject'] ?? ''}',
        type: '${j['type'] ?? 'text'}',
        createdAt: '${j['created_at'] ?? ''}',
      );
}

class SocialPost {
  SocialPost({
    required this.id,
    required this.authorId,
    required this.author,
    required this.username,
    required this.avatar,
    required this.role,
    required this.verified,
    required this.type,
    required this.content,
    required this.subject,
    required this.visibility,
    required this.anonymous,
    required this.createdAt,
    required this.likes,
    required this.dislikes,
    required this.comments,
    required this.reposts,
    required this.solved,
    required this.pinned,
    required this.myReaction,
    required this.saved,
    required this.reposted,
    required this.mine,
    required this.media,
    required this.source,
  });

  final int id, authorId;
  final String author, username, role, type, content, subject, visibility, createdAt;
  final String? avatar;
  final bool verified, anonymous, solved, pinned, mine;
  int likes, dislikes, comments, reposts;
  String? myReaction;
  bool saved, reposted;
  final List<SocialMedia> media;
  final SocialSourcePost? source;

  factory SocialPost.fromJson(Map<String, dynamic> j) => SocialPost(
        id: smInt(j['id']),
        authorId: smInt(j['author_id']),
        author: '${j['author'] ?? ''}',
        username: '${j['username'] ?? ''}',
        avatar: smNullable(j['avatar']),
        role: '${j['role'] ?? 'student'}',
        verified: smBool(j['verified']),
        type: '${j['type'] ?? 'text'}',
        content: '${j['content'] ?? ''}',
        subject: '${j['subject'] ?? ''}',
        visibility: '${j['visibility'] ?? 'public'}',
        anonymous: smBool(j['anonymous']),
        createdAt: '${j['created_at'] ?? ''}',
        likes: smInt(j['likes']),
        dislikes: smInt(j['dislikes']),
        comments: smInt(j['comments']),
        reposts: smInt(j['reposts']),
        solved: smBool(j['solved']),
        pinned: smBool(j['pinned']),
        myReaction: smNullable(j['my_reaction']),
        saved: smBool(j['saved']),
        reposted: smBool(j['reposted']),
        mine: smBool(j['mine']),
        media: smList(j['media'])
            .map((e) => SocialMedia.fromJson(smMap(e)))
            .where((e) => e.url.isNotEmpty)
            .toList(),
        source: j['source'] is Map
            ? SocialSourcePost.fromJson(smMap(j['source']))
            : null,
      );
}

class SocialFeedPage {
  const SocialFeedPage({
    required this.posts,
    required this.hasMore,
    required this.nextBefore,
    required this.subjects,
    required this.showDislikes,
  });
  final List<SocialPost> posts;
  final bool hasMore, showDislikes;
  final int nextBefore;
  final List<String> subjects;

  factory SocialFeedPage.fromJson(Map<String, dynamic> j) => SocialFeedPage(
        posts: smList(j['posts']).map((e) => SocialPost.fromJson(smMap(e))).toList(),
        hasMore: smBool(j['has_more']),
        nextBefore: smInt(j['next_before']),
        subjects: smList(j['subjects']).map((e) => '$e').where((e) => e.isNotEmpty).toList(),
        showDislikes: smBool(j['show_dislikes']),
      );
}

class ProfileData {
  ProfileData({
    required this.id,
    required this.name,
    required this.username,
    required this.role,
    this.avatar,
    this.cover,
    required this.verified,
    required this.verifiedAt,
    required this.verifiedKind,
    required this.headline,
    required this.bio,
    required this.city,
    required this.country,
    required this.posts,
    required this.followers,
    required this.following,
    required this.profilePrivacy,
    required this.private,
    required this.blocked,
    required this.iBlocked,
    required this.blockedMe,
    required this.isMe,
    required this.isFollowing,
    required this.followsYou,
    required this.allowDm,
    required this.level,
    required this.classGrade,
    required this.institute,
    required this.degree,
    required this.department,
    required this.semester,
    required this.subjects,
    required this.qualification,
    required this.experience,
    required this.teaches,
    required this.website,
    required this.acceptingStudents,
    required this.rating,
    required this.ratings,
    required this.phone,
    required this.gender,
    required this.dob,
  });

  final int id;
  final String name, username, role;
  final String? avatar, cover;
  final bool verified;
  final String verifiedAt, verifiedKind, headline, bio, city, country;
  int posts, followers, following;
  final String profilePrivacy;
  final bool private, blocked, iBlocked, blockedMe, isMe, followsYou;
  bool isFollowing;
  final String allowDm, level, classGrade, institute, degree, department, semester;
  final String subjects, qualification, teaches, website, phone, gender, dob;
  final int experience, ratings;
  final bool acceptingStudents;
  final double rating;

  factory ProfileData.fromJson(Map<String, dynamic> j) => ProfileData(
        id: smInt(j['id']),
        name: '${j['name'] ?? ''}',
        username: '${j['username'] ?? ''}',
        role: '${j['role'] ?? 'student'}',
        avatar: smNullable(j['avatar']),
        cover: smNullable(j['cover']),
        verified: smBool(j['verified']),
        verifiedAt: '${j['verified_at'] ?? ''}',
        verifiedKind: '${j['verified_kind'] ?? ''}',
        headline: '${j['headline'] ?? ''}',
        bio: '${j['bio'] ?? ''}',
        city: '${j['city'] ?? ''}',
        country: '${j['country'] ?? ''}',
        posts: smInt(j['posts']),
        followers: smInt(j['followers']),
        following: smInt(j['following']),
        profilePrivacy: '${j['profile_privacy'] ?? 'public'}',
        private: smBool(j['private']),
        blocked: smBool(j['blocked']),
        iBlocked: smBool(j['i_blocked']),
        blockedMe: smBool(j['blocked_me']),
        isMe: smBool(j['is_me']),
        isFollowing: smBool(j['is_following']),
        followsYou: smBool(j['follows_you']),
        allowDm: '${j['allow_dm'] ?? 'everyone'}',
        level: '${j['level'] ?? ''}',
        classGrade: '${j['class_grade'] ?? ''}',
        institute: '${j['institute'] ?? ''}',
        degree: '${j['degree'] ?? ''}',
        department: '${j['department'] ?? ''}',
        semester: '${j['semester'] ?? ''}',
        subjects: '${j['subjects'] ?? ''}',
        qualification: '${j['qualification'] ?? ''}',
        experience: smInt(j['experience']),
        teaches: '${j['teaches'] ?? ''}',
        website: '${j['website'] ?? ''}',
        acceptingStudents: smBool(j['accepting_students']),
        rating: smDouble(j['rating']),
        ratings: smInt(j['ratings']),
        phone: '${j['phone'] ?? ''}',
        gender: '${j['gender'] ?? ''}',
        dob: '${j['dob'] ?? ''}',
      );
}

class ProfileActivityItem {
  const ProfileActivityItem({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.meta,
    required this.kind,
  });
  final int id;
  final String title, subtitle, meta, kind;
  factory ProfileActivityItem.fromJson(Map<String, dynamic> j) => ProfileActivityItem(
        id: smInt(j['id']),
        title: '${j['title'] ?? ''}',
        subtitle: '${j['subtitle'] ?? ''}',
        meta: '${j['meta'] ?? ''}',
        kind: '${j['kind'] ?? ''}',
      );
}

class ProfileActivityPage {
  const ProfileActivityPage({required this.items, required this.hasMore, required this.nextBefore});
  final List<ProfileActivityItem> items;
  final bool hasMore;
  final int nextBefore;
  factory ProfileActivityPage.fromJson(Map<String, dynamic> j) => ProfileActivityPage(
        items: smList(j['items']).map((e) => ProfileActivityItem.fromJson(smMap(e))).toList(),
        hasMore: smBool(j['has_more']),
        nextBefore: smInt(j['next_before']),
      );
}

class VerificationApplication {
  const VerificationApplication({
    required this.id,
    required this.caseId,
    required this.kind,
    required this.status,
    required this.fullName,
    required this.idNumber,
    required this.orgName,
    required this.roleTitle,
    required this.subjects,
    required this.experience,
    required this.website,
    required this.contactPhone,
    required this.notes,
    required this.adminNote,
    required this.attemptNo,
    required this.createdAt,
    required this.viewed,
    required this.reviewed,
    required this.hasDocId,
    required this.hasDocProof,
    required this.hasDocExtra,
  });
  final int id, caseId, experience, attemptNo;
  final String kind, status, fullName, idNumber, orgName, roleTitle, subjects;
  final String website, contactPhone, notes, adminNote, createdAt;
  final bool viewed, reviewed, hasDocId, hasDocProof, hasDocExtra;

  factory VerificationApplication.fromJson(Map<String, dynamic> j) => VerificationApplication(
        id: smInt(j['id']),
        caseId: smInt(j['case_id']),
        kind: '${j['kind'] ?? 'student'}',
        status: '${j['status'] ?? ''}',
        fullName: '${j['full_name'] ?? ''}',
        idNumber: '${j['id_number'] ?? ''}',
        orgName: '${j['org_name'] ?? ''}',
        roleTitle: '${j['role_title'] ?? ''}',
        subjects: '${j['subjects'] ?? ''}',
        experience: smInt(j['experience']),
        website: '${j['website'] ?? ''}',
        contactPhone: '${j['contact_phone'] ?? ''}',
        notes: '${j['notes'] ?? ''}',
        adminNote: '${j['admin_note'] ?? ''}',
        attemptNo: smInt(j['attempt_no']),
        createdAt: '${j['created_at'] ?? ''}',
        viewed: smBool(j['viewed']),
        reviewed: smBool(j['reviewed']),
        hasDocId: smBool(j['has_doc_id']),
        hasDocProof: smBool(j['has_doc_proof']),
        hasDocExtra: smBool(j['has_doc_extra']),
      );
}

class VerificationState {
  const VerificationState({
    required this.emailVerified,
    required this.verified,
    required this.canApply,
    required this.application,
  });
  final bool emailVerified, verified, canApply;
  final VerificationApplication? application;
  factory VerificationState.fromJson(Map<String, dynamic> j) => VerificationState(
        emailVerified: smBool(j['email_verified']),
        verified: smBool(j['verified']),
        canApply: smBool(j['can_apply']),
        application: j['application'] is Map
            ? VerificationApplication.fromJson(smMap(j['application']))
            : null,
      );
}

Map<String, dynamic> smMap(dynamic value) => value is Map<String, dynamic>
    ? value
    : value is Map
        ? value.cast<String, dynamic>()
        : <String, dynamic>{};
List<dynamic> smList(dynamic value) => value is List ? value : const [];
int smInt(dynamic value) => value is int ? value : int.tryParse('$value') ?? 0;
double smDouble(dynamic value) => value is num ? value.toDouble() : double.tryParse('$value') ?? 0;
bool smBool(dynamic value) {
  if (value is bool) return value;
  if (value is num) return value != 0;
  return '$value'.toLowerCase() == 'true' || '$value' == '1';
}
String? smNullable(dynamic value) => value == null || '$value'.isEmpty ? null : '$value';
