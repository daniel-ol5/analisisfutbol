/// Formulario de alta de jugador  —  CU-11 (Criterio 1 y 2).
///
/// Nombre, apellido, dorsal, posición y pie hábil son obligatorios. La altura
/// en cm es obligatoria para asistir en la estimación de escala y modelos de
/// pose física; el peso es opcional.
library;

import 'package:flutter/material.dart';

import '../../../app/tema.dart';
import '../../../shared/api/cliente.dart';
import '../datos/jugador_repository.dart';
import '../modelos.dart';

class FormularioJugador extends StatefulWidget {
  const FormularioJugador({
    super.key,
    required this.equipoId,
    required this.onCreado,
  });

  final int equipoId;
  final ValueChanged<Jugador> onCreado;

  @override
  State<FormularioJugador> createState() => _FormularioJugadorState();
}

class _FormularioJugadorState extends State<FormularioJugador> {
  final _jugadorRepository = const JugadorRepository();

  final _formKey = GlobalKey<FormState>();
  final _nombre = TextEditingController();
  final _apellido = TextEditingController();
  final _dorsal = TextEditingController();
  final _altura = TextEditingController();
  final _peso = TextEditingController();

  String _posicion = 'ARQ';
  String _pieHabil = 'DER';
  bool _guardando = false;
  String? _error;

  @override
  void dispose() {
    _nombre.dispose();
    _apellido.dispose();
    _dorsal.dispose();
    _altura.dispose();
    _peso.dispose();
    super.dispose();
  }

  Future<void> _guardar() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _guardando = true;
      _error = null;
    });
    try {
      final pesoTexto = _peso.text.trim();
      final jugador = await _jugadorRepository.crear(
        widget.equipoId,
        nombre: _nombre.text.trim(),
        apellido: _apellido.text.trim(),
        dorsal: int.parse(_dorsal.text.trim()),
        posicion: _posicion,
        pieHabil: _pieHabil,
        alturaCm: int.parse(_altura.text.trim()),
        pesoKg: pesoTexto.isEmpty ? null : double.parse(pesoTexto),
      );
      if (!mounted) return;
      widget.onCreado(jugador);
      Navigator.pop(context);
    } on ErrorApi catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.pendiente
            ? 'Caso de uso aún no disponible: ${e.detalle}'
            : e.detalle;
        _guardando = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'No se pudo registrar al jugador.';
        _guardando = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 44,
                  height: 4,
                  decoration: BoxDecoration(
                    color: t.colorScheme.outline,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'NUEVO JUGADOR (CU-11)',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 1.0,
                  color: verde,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Completá la ficha técnica para sumarlo al plantel.',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 18),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _nombre,
                      textCapitalization: TextCapitalization.words,
                      decoration: const InputDecoration(labelText: 'Nombre'),
                      validator: (v) =>
                          (v == null || v.trim().isEmpty) ? 'Requerido' : null,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _apellido,
                      textCapitalization: TextCapitalization.words,
                      decoration: const InputDecoration(labelText: 'Apellido'),
                      validator: (v) =>
                          (v == null || v.trim().isEmpty) ? 'Requerido' : null,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _dorsal,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'Dorsal'),
                      validator: (v) {
                        final n = int.tryParse(v?.trim() ?? '');
                        return (n == null || n <= 0) ? 'Número válido' : null;
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _altura,
                      keyboardType: TextInputType.number,
                      decoration:
                          const InputDecoration(labelText: 'Altura (cm)'),
                      validator: (v) {
                        final n = int.tryParse(v?.trim() ?? '');
                        return (n == null || n <= 0) ? 'Requerido' : null;
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _peso,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Peso (kg) · opcional'),
                validator: (v) {
                  if (v == null || v.trim().isEmpty) return null;
                  return double.tryParse(v.trim()) == null ? 'Número válido' : null;
                },
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                initialValue: _posicion,
                decoration: const InputDecoration(labelText: 'Posición'),
                items: [
                  for (final e in etiquetasPosicion.entries)
                    DropdownMenuItem(value: e.key, child: Text(e.value)),
                ],
                onChanged: (v) => setState(() => _posicion = v ?? _posicion),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                initialValue: _pieHabil,
                decoration: const InputDecoration(labelText: 'Pie hábil'),
                items: [
                  for (final e in etiquetasPie.entries)
                    DropdownMenuItem(value: e.key, child: Text(e.value)),
                ],
                onChanged: (v) => setState(() => _pieHabil = v ?? _pieHabil),
              ),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  decoration: BoxDecoration(
                    border: Border.all(color: rojo),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, color: rojo, size: 20),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(_error!,
                            style: const TextStyle(
                                color: rojo, fontWeight: FontWeight.w600)),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 22),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _guardando ? null : _guardar,
                  style: FilledButton.styleFrom(
                    backgroundColor: verde,
                    foregroundColor: Colors.white,
                  ),
                  child: _guardando
                      ? const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white))
                      : const Text('REGISTRAR JUGADOR'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
