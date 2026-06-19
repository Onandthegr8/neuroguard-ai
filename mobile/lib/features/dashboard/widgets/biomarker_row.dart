import 'package:flutter/material.dart';

class BiomarkerRow extends StatelessWidget {
  final double? sleepQuality;
  final double? typingStability;
  final String wearableStatus;

  const BiomarkerRow({super.key, this.sleepQuality, this.typingStability, required this.wearableStatus});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: _BioCard(icon: Icons.bedtime_outlined, label: 'Sleep Quality',
            value: sleepQuality != null ? '${(sleepQuality! * 100).round()}%' : '--', color: Colors.indigo)),
        const SizedBox(width: 8),
        Expanded(child: _BioCard(icon: Icons.keyboard_outlined, label: 'Typing Stability',
            value: typingStability != null ? '${(typingStability! * 100).round()}%' : '--', color: Colors.teal)),
        const SizedBox(width: 8),
        Expanded(child: _BioCard(
            icon: wearableStatus == 'synced' ? Icons.watch_outlined : Icons.watch_off_outlined,
            label: 'Wearable',
            value: wearableStatus == 'synced' ? 'Synced' : 'Offline',
            color: wearableStatus == 'synced' ? Colors.green : Colors.orange)),
      ],
    );
  }
}

class _BioCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _BioCard({required this.icon, required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
          child: Column(
            children: [
              Icon(icon, color: color, size: 28),
              const SizedBox(height: 8),
              Text(value, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: color)),
              const SizedBox(height: 2),
              Text(label, style: const TextStyle(fontSize: 10, color: Colors.grey), textAlign: TextAlign.center),
            ],
          ),
        ),
      );
}
