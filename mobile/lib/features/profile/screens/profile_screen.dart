import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../auth/bloc/auth_bloc.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Profile & Settings', style: TextStyle(fontWeight: FontWeight.bold))),
      body: ListView(
        children: [
          const _SectionHeader('Account'),
          ListTile(leading: const Icon(Icons.person_outline), title: const Text('Personal Information'), trailing: const Icon(Icons.chevron_right)),
          ListTile(leading: const Icon(Icons.security), title: const Text('Privacy & Consent'), trailing: const Icon(Icons.chevron_right)),
          ListTile(leading: const Icon(Icons.download_outlined), title: const Text('Export My Data'), trailing: const Icon(Icons.chevron_right)),
          const Divider(),
          const _SectionHeader('Monitoring'),
          ListTile(leading: const Icon(Icons.watch_outlined), title: const Text('Wearable Devices'), trailing: const Icon(Icons.chevron_right)),
          ListTile(leading: const Icon(Icons.keyboard_outlined), title: const Text('Keystroke Monitoring'), trailing: Switch(value: true, onChanged: (_) {})),
          const Divider(),
          const _SectionHeader('Health'),
          ListTile(leading: const Icon(Icons.local_hospital_outlined), title: const Text('Share with Clinician'), trailing: const Icon(Icons.chevron_right)),
          ListTile(leading: const Icon(Icons.assignment_outlined), title: const Text('Weekly Assessments'), trailing: const Icon(Icons.chevron_right)),
          const Divider(),
          const _SectionHeader('About'),
          ListTile(leading: const Icon(Icons.info_outline), title: const Text('About NeuroGuard'), trailing: const Icon(Icons.chevron_right)),
          ListTile(leading: const Icon(Icons.shield_outlined), title: const Text('Privacy Policy'), trailing: const Icon(Icons.chevron_right)),
          const Divider(),
          Padding(
            padding: const EdgeInsets.all(16),
            child: OutlinedButton.icon(
              icon: const Icon(Icons.logout, color: Colors.red),
              label: const Text('Sign Out', style: TextStyle(color: Colors.red)),
              onPressed: () => context.read<AuthBloc>().add(const AuthLogoutEvent()),
              style: OutlinedButton.styleFrom(side: const BorderSide(color: Colors.red)),
            ),
          ),
          const SizedBox(height: 24),
          Center(child: Text('NeuroGuard AI v1.0.0', style: TextStyle(color: Colors.grey.shade400, fontSize: 12))),
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
        child: Text(title, style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.grey.shade500, letterSpacing: 1.2)),
      );
}
