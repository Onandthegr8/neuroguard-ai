import 'package:flutter/material.dart';

class ReportsScreen extends StatelessWidget {
  const ReportsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reports', style: TextStyle(fontWeight: FontWeight.bold))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('Recent Reports', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 12),
          _ReportTile(title: 'Monthly Summary — April 2026', date: 'Generated May 1, 2026', onTap: () {}),
          _ReportTile(title: 'Monthly Summary — March 2026', date: 'Generated Apr 1, 2026', onTap: () {}),
          const SizedBox(height: 24),
          FilledButton.icon(
            icon: const Icon(Icons.picture_as_pdf),
            label: const Text('Generate New Report'),
            onPressed: () {},
          ),
        ],
      ),
    );
  }
}

class _ReportTile extends StatelessWidget {
  final String title, date;
  final VoidCallback onTap;
  const _ReportTile({required this.title, required this.date, required this.onTap});

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: const CircleAvatar(backgroundColor: Color(0xFFEFF6FF), child: Icon(Icons.description_outlined, color: Color(0xFF1E40AF))),
          title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          subtitle: Text(date, style: const TextStyle(fontSize: 12)),
          trailing: const Icon(Icons.download_outlined, color: Color(0xFF1E40AF)),
          onTap: onTap,
        ),
      );
}
