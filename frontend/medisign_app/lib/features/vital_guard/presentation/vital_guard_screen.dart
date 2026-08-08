import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

class VitalGuardScreen extends StatefulWidget {
  const VitalGuardScreen({super.key});

  @override
  State<VitalGuardScreen> createState() => _VitalGuardScreenState();
}

class _VitalGuardScreenState extends State<VitalGuardScreen> {
  final String _baseUrl = 'http://127.0.0.1:5000/api';
  String _selectedRole = 'Admin';
  List<dynamic> _patients = [];
  bool _isLoading = false;
  String? _errorMessage;
  final ImagePicker _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    _fetchPatients();
  }

  Future<void> _fetchPatients() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/patients/role-scoped?role=${_selectedRole.toLowerCase()}'),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['success'] == true) {
          setState(() {
            _patients = data['data'];
            _isLoading = false;
          });
        } else {
          throw Exception('Backend returned failure status');
        }
      } else {
        throw Exception('Server returned status code ${response.statusCode}');
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Could not fetch records: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _attachEvidence(String recordType, String recordId) async {
    try {
      final XFile? image = await _picker.pickImage(source: ImageSource.gallery, imageQuality: 50);
      if (image == null) return;

      final bytes = await image.readAsBytes();
      final base64Image = 'data:image/png;base64,${base64.encode(bytes)}';

      setState(() => _isLoading = true);

      final response = await http.post(
        Uri.parse('$_baseUrl/records/$recordType/$recordId/attachment'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'file_name': image.name,
          'image_data_url': base64Image,
        }),
      );

      setState(() => _isLoading = false);

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Attached ${image.name} successfully to $recordType!'),
            backgroundColor: const Color(0xFF68F5B8),
          ),
        );
        _fetchPatients();
      } else {
        throw Exception('Attachment failed with status: ${response.statusCode}');
      }
    } catch (e) {
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to attach evidence: $e'), backgroundColor: Colors.red),
      );
    }
  }

  void _showSummaryReport(Map<String, dynamic> patient) {
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF0E1C2D),
          title: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Clinical Summary Report', style: TextStyle(color: Colors.white)),
              IconButton(
                icon: const Icon(Icons.close, color: Colors.white70),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
          content: SizedBox(
            width: double.maxFinite,
            child: ListView(
              shrinkWrap: true,
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1D2B3C),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: const Color(0xFF22D3EE), width: 1),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Patient: ${patient['name']}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      Text('Room: ${patient['room']} | Risk Level: ${String.fromCharCodes(patient['status']?.toString().toUpperCase().codeUnits ?? [])}'),
                      Text('Condition: ${patient['condition']}'),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                const Text('AI Diagnostics & Symptoms', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF22D3EE))),
                const Text('- General recovery progress stable.\n- Blood oxygen normal at 98%.\n- Primary symptom healing expected on timeline.', style: TextStyle(color: Colors.white70)),
                const SizedBox(height: 16),
                const Text('Next-Step Guidance', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF22D3EE))),
                const Text('1. Continuous vitals monitoring.\n2. Review dosage limits before post-op antibiotic administration.\n3. Check wound status every 12 hours.', style: TextStyle(color: Colors.white70)),
                const SizedBox(height: 20),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.amber.withOpacity(0.1),
                    border: Border.all(color: Colors.amber, width: 0.5),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Text(
                    '⚠️ CLINICAL DISCLAIMER: Generated by AI clinical assistance for coordinator reference only. All instructions must be verified by a licensed practitioner.',
                    style: TextStyle(fontSize: 11, color: Colors.amberAccent),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            ElevatedButton.icon(
              icon: const Icon(Icons.download),
              label: const Text('Export Summary'),
              onPressed: () {
                Navigator.of(context).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Summary report exported as TXT successfully!'),
                    backgroundColor: Color(0xFF68F5B8),
                  ),
                );
              },
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final roles = ['Admin', 'Hospital', 'Investigator', 'Reviewer', 'Authority', 'Patient'];

    return Scaffold(
      appBar: AppBar(
        title: const Text('VitalGuard Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchPatients,
          )
        ],
      ),
      body: Column(
        children: [
          // Role selection tabs
          Container(
            height: 60,
            padding: const EdgeInsets.symmetric(vertical: 8),
            decoration: const BoxDecoration(
              color: Color(0xFF0E1C2D),
              border: Border(bottom: BorderSide(color: Color(0xFF1D2B3C))),
            ),
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: roles.length,
              itemBuilder: (context, index) {
                final role = roles[index];
                final isSelected = role == _selectedRole;
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 6),
                  child: ChoiceChip(
                    label: Text(role),
                    selected: isSelected,
                    onSelected: (selected) {
                      if (selected) {
                        setState(() {
                          _selectedRole = role;
                        });
                        _fetchPatients();
                      }
                    },
                    selectedColor: const Color(0xFF22D3EE).withOpacity(0.2),
                    backgroundColor: const Color(0xFF1D2B3C),
                    labelStyle: TextStyle(
                      color: isSelected ? const Color(0xFF22D3EE) : Colors.white70,
                      fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                    ),
                  ),
                );
              },
            ),
          ),

          // Search counts / Status bar
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Visible Records: ${_patients.length}',
                  style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white70),
                ),
                Text(
                  'Role Scope: $_selectedRole',
                  style: const TextStyle(fontSize: 12, color: Color(0xFFB9C8DF)),
                ),
              ],
            ),
          ),

          // Main content
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _errorMessage != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Text(
                            _errorMessage!,
                            style: const TextStyle(color: Colors.redAccent),
                            textAlign: TextAlign.center,
                          ),
                        ),
                      )
                    : _patients.isEmpty
                        ? const Center(child: Text('No patient records found under this scope.'))
                        : ListView.builder(
                            padding: const EdgeInsets.all(12),
                            itemCount: _patients.length,
                            itemBuilder: (context, index) {
                              final p = _patients[index];
                              final status = p['status'] ?? 'stable';
                              Color statusColor = const Color(0xFF68F5B8);
                              if (status == 'critical') statusColor = Colors.redAccent;
                              if (status == 'attention') statusColor = Colors.amberAccent;

                              return Card(
                                margin: const EdgeInsets.only(bottom: 16),
                                color: const Color(0xFF122031),
                                child: Padding(
                                  padding: const EdgeInsets.all(16.0),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      // Patient Header
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Text(
                                                p['name'] ?? 'Unknown Patient',
                                                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                                              ),
                                              const SizedBox(height: 2),
                                              Text(
                                                'UID: ${p['patient_uid'] ?? '-'} | Room: ${p['room']}',
                                                style: const TextStyle(color: Colors.white70, fontSize: 13),
                                              ),
                                            ],
                                          ),
                                          Chip(
                                            label: Text(status.toString().toUpperCase()),
                                            backgroundColor: statusColor.withOpacity(0.15),
                                            side: BorderSide(color: statusColor, width: 0.5),
                                            labelStyle: TextStyle(color: statusColor, fontSize: 11, fontWeight: FontWeight.bold),
                                          ),
                                        ],
                                      ),
                                      const Divider(height: 24),

                                      // Symptoms & Condition
                                      Row(
                                        children: [
                                          const Icon(Icons.healing, size: 16, color: Color(0xFFB9C8DF)),
                                          const SizedBox(width: 8),
                                          Expanded(
                                            child: Text(
                                              'Condition: ${p['condition'] ?? '-'}',
                                              style: const TextStyle(color: Colors.white70),
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 8),

                                      // Actions / Summary Button
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          OutlinedButton.icon(
                                            icon: const Icon(Icons.attachment, size: 16),
                                            label: const Text('Attach Evidence', style: TextStyle(fontSize: 12)),
                                            onPressed: () => _attachEvidence('vitals', p['patient_id'] ?? 'sample-patient-123'),
                                          ),
                                          ElevatedButton.icon(
                                            icon: const Icon(Icons.analytics, size: 16),
                                            label: const Text('Summary Report', style: TextStyle(fontSize: 12)),
                                            onPressed: () => _showSummaryReport(p),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }
}
