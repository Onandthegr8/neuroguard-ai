import 'package:flutter/material.dart';

class SleepScreen extends StatelessWidget {
  const SleepScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sleep Insights', style: TextStyle(fontWeight: FontWeight.bold))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _SleepMetricCard(label: 'Sleep Efficiency', value: '82%', icon: Icons.nightlight_round, color: Colors.indigo,
              description: 'Time asleep vs. time in bed'),
          _SleepMetricCard(label: 'REM Duration', value: '94 min', icon: Icons.waves, color: Colors.purple,
              description: 'REM sleep duration last night'),
          _SleepMetricCard(label: 'REM Fragmentation', value: '0.18', icon: Icons.broken_image_outlined, color: Colors.orange,
              description: 'Lower is better. >0.5 warrants attention.'),
          _SleepMetricCard(label: 'HRV (RMSSD)', value: '42 ms', icon: Icons.favorite_outline, color: Colors.red,
              description: 'Heart rate variability — higher is better'),
          _SleepMetricCard(label: 'Stage Transitions', value: '18', icon: Icons.swap_vert, color: Colors.teal,
              description: 'Sleep stage transitions last night'),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('AI Sleep Note', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                const SizedBox(height: 8),
                Text('Your REM fragmentation score is within the normal range. Consistent sleep patterns over the past 7 days.',
                    style: TextStyle(color: Colors.grey.shade700, height: 1.5)),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}

class _SleepMetricCard extends StatelessWidget {
  final String label, value, description;
  final IconData icon;
  final Color color;
  const _SleepMetricCard({required this.label, required this.value, required this.icon, required this.color, required this.description});

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: CircleAvatar(backgroundColor: color.withOpacity(0.12), child: Icon(icon, color: color)),
          title: Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text(description, style: const TextStyle(fontSize: 12)),
          trailing: Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: color)),
        ),
      );
}
