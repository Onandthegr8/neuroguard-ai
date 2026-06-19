import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/network/api_client.dart';

const _apiBase = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://api.neuroguard.health/api/v1',
);

class _VendorInfo {
  final String vendor;
  final String name;
  final String subtitle;
  final IconData icon;
  final Color  color;
  final bool   oauthSupported;

  const _VendorInfo({
    required this.vendor,
    required this.name,
    required this.subtitle,
    required this.icon,
    required this.color,
    this.oauthSupported = false,
  });
}

const _vendors = [
  _VendorInfo(
    vendor:         'fitbit',
    name:           'Fitbit',
    subtitle:       'Sense, Versa, Charge — sleep + HRV',
    icon:           Icons.monitor_heart,
    color:          Color(0xFF00B0B9),
    oauthSupported: true,
  ),
  _VendorInfo(
    vendor:  'apple',
    name:    'Apple Watch',
    subtitle:'Requires HealthKit permission on device',
    icon:    Icons.watch,
    color:   Color(0xFF1D1D1F),
  ),
  _VendorInfo(
    vendor:  'oura',
    name:    'Oura Ring',
    subtitle:'Gen 3 — REM, HRV, readiness',
    icon:    Icons.circle_outlined,
    color:   Color(0xFFB5A642),
  ),
  _VendorInfo(
    vendor:  'samsung',
    name:    'Samsung Galaxy Watch',
    subtitle:'Health platform integration',
    icon:    Icons.watch_outlined,
    color:   Color(0xFF1428A0),
  ),
  _VendorInfo(
    vendor:  'garmin',
    name:    'Garmin',
    subtitle:'Connect IQ API — coming soon',
    icon:    Icons.gps_fixed,
    color:   Color(0xFF007CC3),
  ),
];

class WearablePairingScreen extends StatefulWidget {
  final ApiClient apiClient;

  const WearablePairingScreen({super.key, required this.apiClient});

  @override
  State<WearablePairingScreen> createState() => _WearablePairingScreenState();
}

class _WearablePairingScreenState extends State<WearablePairingScreen> {
  bool                     _loadingList = true;
  bool                     _syncing     = false;
  List<Map<String, dynamic>> _connected = [];
  String?                  _error;

  @override
  void initState() {
    super.initState();
    _loadConnected();
  }

  Future<void> _loadConnected() async {
    setState(() { _loadingList = true; _error = null; });
    try {
      final resp = await widget.apiClient.get<List<dynamic>>('/wearable/list');
      final list = (resp.data ?? []).cast<Map<String, dynamic>>();
      if (mounted) setState(() { _connected = list; _loadingList = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loadingList = false; });
    }
  }

  bool _isConnected(String vendor) =>
      _connected.any((w) => w['vendor'] == vendor);

  Future<void> _connectFitbit() async {
    final url = Uri.parse('$_apiBase/wearable/fitbit/connect');
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
      // Refresh list when user returns to the app
      await Future.delayed(const Duration(seconds: 2));
      await _loadConnected();
    } else {
      _showError('Could not open browser for Fitbit authorization.');
    }
  }

  Future<void> _syncFitbit() async {
    setState(() => _syncing = true);
    try {
      final resp = await widget.apiClient.post<Map<String, dynamic>>(
        '/wearable/fitbit/sync',
        data: {'days': 7},
      );
      final data = resp.data ?? {};
      final synced  = data['synced_count']  ?? 0;
      final skipped = data['skipped_count'] ?? 0;
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Synced $synced new nights ($skipped already stored)'),
          backgroundColor: Colors.green.shade700,
        ));
      }
    } catch (e) {
      _showError('Sync failed: $e');
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  void _showError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: Colors.red.shade700),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Wearable Devices', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadConnected),
        ],
      ),
      body: _loadingList
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Info card
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEFF6FF),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.info_outline, color: Color(0xFF1E40AF), size: 20),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Sleep data (REM cycles, HRV, movement) '
                          'improves Parkinson\'s risk prediction accuracy by ~18%.',
                          style: TextStyle(color: Colors.blue.shade800, fontSize: 13, height: 1.5),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),

                if (_error != null)
                  Container(
                    padding: const EdgeInsets.all(12),
                    margin: const EdgeInsets.only(bottom: 16),
                    decoration: BoxDecoration(
                      color: Colors.red.shade50,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(_error!, style: TextStyle(color: Colors.red.shade700, fontSize: 13)),
                  ),

                // Vendor list
                for (final v in _vendors) _vendorCard(v),
              ],
            ),
    );
  }

  Widget _vendorCard(_VendorInfo v) {
    final connected = _isConnected(v.vendor);
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: connected ? v.color : Colors.grey.shade200),
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2)),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            // Icon circle
            Container(
              width: 48, height: 48,
              decoration: BoxDecoration(
                color: v.color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(v.icon, color: v.color, size: 24),
            ),
            const SizedBox(width: 14),

            // Labels
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(v.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                      if (connected) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.green.shade100,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text('Connected', style: TextStyle(color: Colors.green.shade700, fontSize: 11, fontWeight: FontWeight.w600)),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(v.subtitle, style: TextStyle(color: Colors.grey.shade600, fontSize: 12)),
                ],
              ),
            ),

            // Action button
            if (v.vendor == 'fitbit') ...[
              if (connected)
                _syncing
                  ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2))
                  : TextButton.icon(
                      onPressed: _syncFitbit,
                      icon: const Icon(Icons.sync, size: 16),
                      label: const Text('Sync'),
                      style: TextButton.styleFrom(foregroundColor: v.color),
                    )
              else
                ElevatedButton(
                  onPressed: _connectFitbit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: v.color,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  child: const Text('Connect', style: TextStyle(fontSize: 13)),
                ),
            ] else ...[
              OutlinedButton(
                onPressed: () => _showError('${v.name} integration coming in Phase 3'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.grey.shade600,
                  side: BorderSide(color: Colors.grey.shade300),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                child: const Text('Soon', style: TextStyle(fontSize: 13)),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
