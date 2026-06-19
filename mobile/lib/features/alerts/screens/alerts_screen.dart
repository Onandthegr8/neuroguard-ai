import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/alerts_bloc.dart';
import '../../../core/theme/app_theme.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});
  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  @override
  void initState() {
    super.initState();
    context.read<AlertsBloc>().add(const AlertsLoadEvent());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Alerts', style: TextStyle(fontWeight: FontWeight.bold))),
      body: BlocBuilder<AlertsBloc, AlertsState>(
        builder: (context, state) {
          if (state is AlertsLoading) return const Center(child: CircularProgressIndicator());
          if (state is AlertsError)   return Center(child: Text(state.message));
          if (state is AlertsLoaded) {
            if (state.alerts.isEmpty) {
              return const Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                Icon(Icons.check_circle_outline, size: 64, color: Colors.green),
                SizedBox(height: 16),
                Text('No alerts — all clear!'),
              ]));
            }
            return ListView.builder(
              itemCount: state.alerts.length,
              itemBuilder: (_, i) {
                final alert = state.alerts[i];
                final severity = alert['severity'] as String? ?? 'info';
                return Card(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: AppTheme.riskTierColor(severity == 'critical' ? 'very_high' : severity == 'warning' ? 'moderate' : 'very_low').withOpacity(0.15),
                      child: Icon(
                        severity == 'critical' ? Icons.warning_amber : severity == 'warning' ? Icons.info_outline : Icons.notifications_none,
                        color: AppTheme.riskTierColor(severity == 'critical' ? 'very_high' : severity == 'warning' ? 'moderate' : 'very_low'),
                      ),
                    ),
                    title: Text(alert['title'] as String? ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text(alert['body'] as String? ?? ''),
                    trailing: Text(alert['created_at'] as String? ?? '', style: const TextStyle(fontSize: 10, color: Colors.grey)),
                  ),
                );
              },
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}
