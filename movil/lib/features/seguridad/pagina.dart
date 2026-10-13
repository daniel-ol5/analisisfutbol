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
  bool _sesionActiva = false;
  bool _cargando = false;
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
    setState(() {
      _sesionActiva = activa;
      _verificandoSesion = false;
    });
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
      setState(() {
        _sesionActiva = true;
        _cargando = false;
      });
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

  Future<void> _cerrarSesion() async {
    setState(() => _cargando = true);
    try {
      await seguridad_api.cerrarSesion();
    } catch (_) {
      // El token local ya se borra dentro de cerrarSesion() aunque falle la
      // llamada al backend: no bloquear el cierre de sesión por eso.
    }
    if (!mounted) return;
    setState(() {
      _sesionActiva = false;
      _cargando = false;
      _password.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Seguridad y Administración', style: TextStyle(fontSize: 18)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/'),
        ),
      ),
      body: _verificandoSesion
          ? const Center(child: CircularProgressIndicator())
          : _sesionActiva
              ? _vistaSesionActiva(t)
              : _vistaLogin(t),
    );
  }

  Widget _vistaSesionActiva(ThemeData t) => ListView(
        padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
        children: [
          const Text('P1',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: verde)),
          const SizedBox(height: 10),
          Text('Sesión iniciada.', style: t.textTheme.bodyLarge),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _cargando ? null : _cerrarSesion,
            child: _cargando
                ? const SizedBox(
                    width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Cerrar sesión'),
          ),
        ],
      );

  Widget _vistaLogin(ThemeData t) => Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
          children: [
            const Text('P1',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: verde)),
            const SizedBox(height: 10),
            Text('CU-02 · Iniciar sesión', style: t.textTheme.bodyLarge),
            const SizedBox(height: 18),
            TextFormField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(labelText: 'Correo electrónico'),
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Ingresá tu correo' : null,
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: _password,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Contraseña'),
              validator: (v) =>
                  (v == null || v.isEmpty) ? 'Ingresá tu contraseña' : null,
            ),
            if (_error != null) ...[
              const SizedBox(height: 14),
              Text(_error!, style: const TextStyle(color: rojo)),
            ],
            const SizedBox(height: 20),
            FilledButton(
              onPressed: _cargando ? null : _iniciarSesion,
              child: _cargando
                  ? const SizedBox(
                      width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Iniciar sesión'),
            ),
          ],
        ),
      );
}
