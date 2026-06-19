import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../bloc/keystroke_bloc.dart';
import '../services/keyboard_service.dart';

/// A compact widget shown on the Dashboard home screen.
/// Displays whether keystroke monitoring is active, and lets the user enable
/// it if the AccessibilityService / keyboard extension is not yet set up.
class KeystrokeStatusWidget extends StatelessWidget {
  final KeyboardService keyboardService;

  const KeystrokeStatusWidget({super.key, required this.keyboardService});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<KeystrokeBloc, KeystrokeState>(
      builder: (context, state) {
        return FutureBuilder<bool>(
          future:  keyboardService.isServiceActive(),
          builder: (ctx, snap) {
            final active = snap.data ?? false;
            return _buildCard(context, active, state);
          },
        );
      },
    );
  }

  Widget _buildCard(BuildContext context, bool active, KeystrokeState state) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.06), blurRadius: 12, offset: const Offset(0, 4)),
        ],
      ),
      child: Row(
        children: [
          // Status indicator dot
          Container(
            width: 12, height: 12,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: active ? const Color(0xFF22C55E) : const Color(0xFFEF4444),
            ),
          ),
          const SizedBox(width: 12),

          // Labels
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  active ? 'Keystroke Monitoring Active' : 'Keystroke Monitoring Off',
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                ),
                const SizedBox(height: 2),
                Text(
                  _statusSubtitle(state),
                  style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12),
                ),
              ],
            ),
          ),

          // Action button
          if (!active)
            GestureDetector(
              onTap: () => keyboardService.requestPermission(),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFF1E3A5F),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text('Enable', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
              ),
            )
          else if (state is KeystrokeUploading)
            const SizedBox(
              width: 20, height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          else if (state is KeystrokeUploadSuccess)
            const Icon(Icons.cloud_done_rounded, color: Color(0xFF22C55E), size: 20)
          else
            const Icon(Icons.keyboard_alt_outlined, color: Color(0xFF6B7280), size: 20),
        ],
      ),
    );
  }

  String _statusSubtitle(KeystrokeState state) {
    if (state is KeystrokeUploading)     return 'Uploading session data…';
    if (state is KeystrokeUploadSuccess) return 'Session synced (quality: ${(state.qualityScore * 100).toStringAsFixed(0)}%)';
    if (state is KeystrokeUploadFailed)  return 'Saved offline — will retry';
    return 'Passively collecting typing patterns';
  }
}
