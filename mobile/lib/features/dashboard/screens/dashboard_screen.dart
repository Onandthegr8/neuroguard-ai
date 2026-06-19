import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../bloc/dashboard_bloc.dart';
import '../widgets/wellness_score_card.dart';
import '../widgets/risk_tier_badge.dart';
import '../widgets/biomarker_row.dart';
import '../../alerts/screens/alerts_screen.dart';
import '../../sleep/screens/sleep_screen.dart';
import '../../profile/screens/profile_screen.dart';
import '../../reports/screens/reports_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _tab = 0;

  final _tabs = const [
    _HomeTab(),
    AlertsScreen(),
    ReportsScreen(),
    ProfileScreen(),
  ];

  @override
  void initState() {
    super.initState();
    context.read<DashboardBloc>().add(const DashboardLoadEvent());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _tabs[_tab],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.notifications_outlined), selectedIcon: Icon(Icons.notifications), label: 'Alerts'),
          NavigationDestination(icon: Icon(Icons.description_outlined), selectedIcon: Icon(Icons.description), label: 'Reports'),
          NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }
}

class _HomeTab extends StatelessWidget {
  const _HomeTab();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('NeuroGuard', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(icon: const Icon(Icons.bedtime_outlined), onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SleepScreen()))),
        ],
      ),
      body: BlocBuilder<DashboardBloc, DashboardState>(
        builder: (context, state) {
          if (state is DashboardLoading) return const Center(child: CircularProgressIndicator());
          if (state is DashboardError)  return Center(child: Text(state.message));
          if (state is DashboardLoaded) {
            return RefreshIndicator(
              onRefresh: () async => context.read<DashboardBloc>().add(const DashboardLoadEvent()),
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  WellnessScoreCard(score: state.wellnessScore, riskTier: state.riskTier, riskScore: state.riskScore),
                  const SizedBox(height: 12),
                  BiomarkerRow(
                    sleepQuality: state.sleepQuality,
                    typingStability: state.typingStability,
                    wearableStatus: state.wearableStatus,
                  ),
                  const SizedBox(height: 12),
                  if (state.topInsight != null)
                    Card(
                      child: ListTile(
                        leading: const Icon(Icons.lightbulb_outline, color: Color(0xFF1E40AF)),
                        title: const Text('AI Insight', style: TextStyle(fontWeight: FontWeight.bold)),
                        subtitle: Text(state.topInsight!),
                      ),
                    ),
                ],
              ),
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}
