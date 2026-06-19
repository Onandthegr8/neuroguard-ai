import 'package:flutter/material.dart';

import 'login_screen.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});
  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _pageController = PageController();
  int _currentPage = 0;

  final _pages = const [
    _OnboardingPage(
      icon: Icons.psychology_outlined,
      title: 'Early Detection Saves Lives',
      body: 'NeuroGuard AI passively monitors subtle neurological signals during your daily phone use — no extra effort needed.',
    ),
    _OnboardingPage(
      icon: Icons.keyboard_outlined,
      title: 'Keystroke Intelligence',
      body: 'We analyze typing rhythm and timing patterns — never message content — to detect early motor changes linked to Parkinson\'s.',
    ),
    _OnboardingPage(
      icon: Icons.bedtime_outlined,
      title: 'Sleep Biomarkers',
      body: 'REM sleep fragmentation is one of the earliest Parkinson\'s indicators. Your wearable data tells the story.',
    ),
    _OnboardingPage(
      icon: Icons.security_outlined,
      title: 'Privacy by Design',
      body: 'Federated learning means your raw health data never leaves your device. We only learn from patterns, never from personal data.',
    ),
    _OnboardingPage(
      icon: Icons.local_hospital_outlined,
      title: 'Connected Care',
      body: 'Share AI-generated risk reports with your neurologist for evidence-based conversations and early intervention.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: PageView.builder(
                controller: _pageController,
                itemCount: _pages.length,
                onPageChanged: (i) => setState(() => _currentPage = i),
                itemBuilder: (_, i) => _pages[i],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(_pages.length, (i) => _Dot(active: i == _currentPage)),
                  ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: () {
                      if (_currentPage < _pages.length - 1) {
                        _pageController.nextPage(duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
                      } else {
                        Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
                      }
                    },
                    child: Text(_currentPage < _pages.length - 1 ? 'Next' : 'Get Started'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OnboardingPage extends StatelessWidget {
  final IconData icon;
  final String title;
  final String body;
  const _OnboardingPage({required this.icon, required this.title, required this.body});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 100, color: const Color(0xFF1E40AF)),
            const SizedBox(height: 40),
            Text(title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold), textAlign: TextAlign.center),
            const SizedBox(height: 16),
            Text(body, style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: Colors.grey.shade600, height: 1.6), textAlign: TextAlign.center),
          ],
        ),
      );
}

class _Dot extends StatelessWidget {
  final bool active;
  const _Dot({required this.active});
  @override
  Widget build(BuildContext context) => AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        margin: const EdgeInsets.symmetric(horizontal: 4),
        width: active ? 24 : 8,
        height: 8,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(4),
          color: active ? const Color(0xFF1E40AF) : Colors.grey.shade300,
        ),
      );
}
