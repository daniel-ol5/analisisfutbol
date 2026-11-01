/// Seguridad y Administración  —  P1
///
/// CU-02 Iniciar sesión / CU-03 Cerrar sesión. El resto de los casos de uso
/// de este paquete (CU-01, CU-04, CU-05) siguen pendientes.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tema.dart';
import '../../shared/api/almacenamiento.dart';
import '../../shared/api/cliente.dart';
import 'api.dart' as seguridad_api;

class SeguridadPagina extends StatefulWidget {
  const SeguridadPagina({super.key});

  @override
  State<SeguridadPagina> createState() => _SeguridadPaginaState();
}

class _SeguridadPaginaState extends State<SeguridadPagina> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();

  bool _verificandoSesion = true;
  bool _cargando = false;
  bool _ocultarPassword = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _verificarSesion();
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _verificarSesion() async {
    final activa = await Almacenamiento.haySesion();
    if (!mounted) return;
    if (activa) {
      context.go('/');
      return;
    }
    setState(() => _verificandoSesion = false);
  }

  Future<void> _iniciarSesion() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      await seguridad_api.iniciarSesion(_email.text.trim(), _password.text);
      if (!mounted) return;
      context.go('/');
    } on ErrorApi catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.pendiente ? 'Caso de uso aún no disponible: ${e.detalle}' : e.detalle;
        _cargando = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'No se pudo conectar con el servidor.';
        _cargando = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: _verificandoSesion
            ? const Center(child: CircularProgressIndicator())
            : _vistaLogin(t),
      ),
    );
  }

  Widget _cabecera(ThemeData t, String etiqueta, List<TextSpan> titulo, String subtitulo) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(etiqueta,
              style: t.textTheme.bodySmall?.copyWith(
                  fontSize: 11,
                  letterSpacing: 1.6,
                  fontWeight: FontWeight.w700,
                  color: t.colorScheme.outline)),
          const SizedBox(height: 10),
          Text.rich(TextSpan(children: titulo), style: t.textTheme.titleLarge?.copyWith(fontSize: 30)),
          const SizedBox(height: 6),
          Text(subtitulo,
              style: t.textTheme.bodyMedium?.copyWith(color: t.colorScheme.onSurfaceVariant)),
        ],
      );

  Widget _vistaLogin(ThemeData t) => Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
          children: [
            _cabecera(
              t,
              'P1 · SEGURIDAD Y ADMINISTRACIÓN',
              [
                const TextSpan(text: 'Iniciar '),
                TextSpan(text: 'sesión', style: TextStyle(color: verde)),
              ],
              'CU-02 · Ingresá con tu correo y contraseña para continuar.',
            ),
            const SizedBox(height: 22),
            Card(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(18, 20, 18, 22),
                child: Column(
                  children: [
                    TextFormField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(
                        labelText: 'Correo electrónico',
                        prefixIcon: Icon(Icons.person_outline),
                      ),
                      validator: (v) =>
                          (v == null || v.trim().isEmpty) ? 'Ingresá tu correo' : null,
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _password,
                      obscureText: _ocultarPassword,
                      textInputAction: TextInputAction.done,
                      onFieldSubmitted: (_) => _cargando ? null : _iniciarSesion(),
                      decoration: InputDecoration(
                        labelText: 'Contraseña',
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          icon: Icon(_ocultarPassword
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined),
                          onPressed: () =>
                              setState(() => _ocultarPassword = !_ocultarPassword),
                        ),
                      ),
                      validator: (v) =>
                          (v == null || v.isEmpty) ? 'Ingresá tu contraseña' : null,
                    ),
                  ],
                ),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
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
                          style: const TextStyle(color: rojo, fontWeight: FontWeight.w600)),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 22),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _cargando ? null : _iniciarSesion,
                child: _cargando
                    ? const SizedBox(
                        width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Iniciar sesión'),
              ),
            ),
          ],
        ),
      );
}
