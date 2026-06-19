import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';

class WellnessScoreCard extends StatelessWidget {
  final int score;
  final String riskTier;
  final double riskScore;

  const WellnessScoreCard({super.key, required this.score, required this.riskTier, required this.riskScore});

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.riskTierColor(riskTier);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Row(
          children: [
            SizedBox(
              width: 90,
              height: 90,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  CircularProgressIndicator(value: score / 100, strokeWidth: 8, color: color, backgroundColor: color.withOpacity(0.15)),
                  Text('$score', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: color)),
                ],
              ),
            ),
            const SizedBox(width: 20),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Neurological Wellness', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  RiskTierBadge(tier: riskTier),
                  const SizedBox(height: 8),
                  Text('AI Risk Score: ${(riskScore * 100).toStringAsFixed(1)}%',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class RiskTierBadge extends StatelessWidget {
  final String tier;
  const RiskTierBadge({super.key, required this.tier});

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.riskTierColor(tier);
    final label = tier.replaceAll('_', ' ').toUpperCase();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(20)),
      child: Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: color)),
    );
  }
}
