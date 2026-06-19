/// OfflineKeystrokeQueue
///
/// SQLite-backed queue that stores keystroke sessions when the device is offline
/// or the upload fails. A background worker drains the queue when connectivity
/// is restored.

import 'dart:convert';
import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

import '../../../core/network/api_client.dart';

class QueuedSession {
  final int?   id;
  final String deviceId;
  final String payload; // JSON encoded
  final int    createdAt; // unix ms

  const QueuedSession({
    this.id,
    required this.deviceId,
    required this.payload,
    required this.createdAt,
  });

  Map<String, dynamic> toMap() => {
    if (id != null) 'id': id,
    'device_id':   deviceId,
    'payload':     payload,
    'created_at':  createdAt,
  };

  factory QueuedSession.fromMap(Map<String, dynamic> m) => QueuedSession(
    id:         m['id'] as int?,
    deviceId:   m['device_id'] as String,
    payload:    m['payload'] as String,
    createdAt:  m['created_at'] as int,
  );
}

class OfflineKeystrokeQueue {
  static const _dbName  = 'neuroguard_queue.db';
  static const _table   = 'keystroke_queue';
  static const _maxRows = 500; // cap at 500 sessions to bound disk usage

  Database? _db;

  Future<Database> get _database async {
    _db ??= await _openDb();
    return _db!;
  }

  Future<Database> _openDb() async {
    final path = join(await getDatabasesPath(), _dbName);
    return openDatabase(
      path,
      version: 1,
      onCreate: (db, _) => db.execute('''
        CREATE TABLE $_table (
          id          INTEGER PRIMARY KEY AUTOINCREMENT,
          device_id   TEXT    NOT NULL,
          payload     TEXT    NOT NULL,
          created_at  INTEGER NOT NULL
        )
      '''),
    );
  }

  /// Enqueue a session payload for later upload.
  Future<void> enqueue({
    required String deviceId,
    required Map<String, dynamic> payload,
  }) async {
    final db = await _database;

    // Evict oldest rows when over cap
    final count = Sqflite.firstIntValue(
      await db.rawQuery('SELECT COUNT(*) FROM $_table'),
    ) ?? 0;
    if (count >= _maxRows) {
      await db.execute(
        'DELETE FROM $_table WHERE id IN '
        '(SELECT id FROM $_table ORDER BY created_at ASC LIMIT ?)',
        [count - _maxRows + 1],
      );
    }

    await db.insert(_table, QueuedSession(
      deviceId:  deviceId,
      payload:   jsonEncode(payload),
      createdAt: DateTime.now().millisecondsSinceEpoch,
    ).toMap());
  }

  /// Return up to [limit] oldest queued sessions.
  Future<List<QueuedSession>> peek({int limit = 10}) async {
    final db = await _database;
    final rows = await db.query(
      _table,
      orderBy: 'created_at ASC',
      limit:   limit,
    );
    return rows.map(QueuedSession.fromMap).toList();
  }

  /// Delete a successfully uploaded session by its DB id.
  Future<void> remove(int id) async {
    final db = await _database;
    await db.delete(_table, where: 'id = ?', whereArgs: [id]);
  }

  Future<int> pendingCount() async {
    final db = await _database;
    return Sqflite.firstIntValue(
          await db.rawQuery('SELECT COUNT(*) FROM $_table'),
        ) ?? 0;
  }

  // ── Drain worker ─────────────────────────────────────────────────────────────

  /// Attempt to upload all queued sessions in batches of 10.
  /// Call this when the app regains connectivity.
  Future<void> drain(ApiClient apiClient) async {
    while (true) {
      final sessions = await peek(limit: 10);
      if (sessions.isEmpty) break;

      for (final s in sessions) {
        try {
          final payload = jsonDecode(s.payload) as Map<String, dynamic>;
          await apiClient.post('/keystroke/features', data: payload);
          await remove(s.id!);
        } catch (_) {
          // Network still unavailable — stop drain and try again later.
          return;
        }
      }
    }
  }
}
