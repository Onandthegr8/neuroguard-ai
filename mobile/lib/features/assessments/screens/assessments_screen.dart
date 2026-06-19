import 'package:flutter/material.dart';

class AssessmentsScreen extends StatelessWidget {
  const AssessmentsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Weekly Assessments', style: TextStyle(fontWeight: FontWeight.bold))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('Optional weekly motor tests help improve AI accuracy.', style: TextStyle(color: Colors.grey)),
          const SizedBox(height: 16),
          _AssessmentCard(
            icon: Icons.touch_app_outlined,
            title: 'Finger Tapping Test',
            description: 'Tap as fast as possible for 10 seconds. Measures motor speed.',
            duration: '~30 sec',
            onStart: () {},
          ),
          _AssessmentCard(
            icon: Icons.gesture,
            title: 'Spiral Drawing',
            description: 'Draw a spiral on screen. Detects hand tremor.',
            duration: '~1 min',
            onStart: () {},
          ),
          _AssessmentCard(
            icon: Icons.mic_outlined,
            title: 'Voice Recording',
            description: 'Sustain "ahhh" for 5 seconds. Captures vocal tremor biomarkers.',
            duration: '~30 sec',
            onStart: () {},
          ),
          _AssessmentCard(
            icon: Icons.directions_walk_outlined,
            title: 'Gait & Balance',
            description: 'Walk normally for 10 steps with your phone in hand.',
            duration: '~1 min',
            onStart: () {},
          ),
          _AssessmentCard(
            icon: Icons.flash_on_outlined,
            title: 'Reaction Time',
            description: 'Tap the screen as soon as the circle appears.',
            duration: '~1 min',
            onStart: () {},
          ),
        ],
      ),
    );
  }
}

class _AssessmentCard extends StatelessWidget {
  final IconData icon;
  final String title, description, duration;
  final VoidCallback onStart;

  const _AssessmentCard({
    required this.icon, required this.title,
    required this.description, required this.duration, required this.onStart,
  });

  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              CircleAvatar(
                radius: 28,
                backgroundColor: const Color(0xFFEFF6FF),
                child: Icon(icon, color: const Color(0xFF1E40AF), size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                  const SizedBox(height: 4),
                  Text(description, style: TextStyle(color: Colors.grey.shade600, fontSize: 12, height: 1.4)),
                  const SizedBox(height: 4),
                  Text(duration, style: const TextStyle(fontSize: 11, color: Color(0xFF1E40AF), fontWeight: FontWeight.w600)),
                ]),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: onStart,
                style: FilledButton.styleFrom(
                  minimumSize: const Size(56, 36),
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                ),
                child: const Text('Start'),
              ),
            ],
          ),
        ),
      );
}
