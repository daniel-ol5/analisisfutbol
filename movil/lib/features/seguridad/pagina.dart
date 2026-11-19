/// Seguridad y Administración  —  P1
///
/// CU-02 Iniciar sesión / CU-03 Cerrar sesión.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../shared/api/almacenamiento.dart';
import '../../shared/api/cliente.dart';
import '../../shared/ui/marca.dart';
import 'api.dart' as seguridad_api;
import 'validacion.dart';

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
    try {
      final activa = await Almacenamiento.haySesion();
      if (!mounted) return;
      if (activa) {
        context.go('/');
        return;
      }
    } catch (_) {}
    if (mounted) {
      setState(() => _verificandoSesion = false);
    }
  }

  Future<void> _iniciarSesion() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      await seguridad_api.iniciarSesion(
        _email.text.trim().toLowerCase(),
        _password.text,
      );
      if (!mounted) return;
      context.go('/');
    } on ErrorApi catch (e) {
      if (!mounted) return;
      setState(() {
        _error = switch (e.codigo) {
          401 => 'Correo o contraseña incorrectos.',
          403 => 'La cuenta está desactivada.',
          422 => 'Ingresa un correo electrónico con formato válido.',
          501 => 'El inicio de sesión no está disponible en este momento.',
          _ => e.detalle,
        };
      });
    } on TimeoutException {
      if (!mounted) return;
      setState(() {
        _error = 'El servidor tardó en responder. Intenta de nuevo.';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'No se pudo conectar. Revisa tu conexión e intenta de nuevo.';
      });
    } finally {
      if (mounted) {
        setState(() => _cargando = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: _verificandoSesion
            ? const Center(child: CircularProgressIndicator())
            : Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 440),
                  child: _vistaLogin(t),
                ),
              ),
      ),
    );
  }

  Widget _vistaLogin(ThemeData t) => Form(
    key: _formKey,
    child: ListView(
      shrinkWrap: true,
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
      children: [
        Row(
          children: [
            const SelloArea(),
            const SizedBox(width: 10),
            Text('Área Técnica', style: t.textTheme.titleMedium),
          ],
        ),
        const SizedBox(height: 18),
        Text('Iniciar sesión', style: t.textTheme.headlineSmall),
        const SizedBox(height: 22),
        Card(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(18, 20, 18, 22),
            child: Column(
              children: [
                TextFormField(
                  controller: _email,
                  autofillHints: const [AutofillHints.username],
                  keyboardType: TextInputType.emailAddress,
                  textInputAction: TextInputAction.next,
                  decoration: const InputDecoration(
                    labelText: 'Correo electrónico',
                    prefixIcon: Icon(Icons.person_outline),
                  ),
                  validator: validarEmail,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _password,
                  autofillHints: const [AutofillHints.password],
                  obscureText: _ocultarPassword,
                  textInputAction: TextInputAction.done,
                  onFieldSubmitted: (_) => _cargando ? null : _iniciarSesion(),
                  decoration: InputDecoration(
                    labelText: 'Contraseña',
                    prefixIcon: const Icon(Icons.lock_outline),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _ocultarPassword
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                      ),
                      onPressed: () =>
                          setState(() => _ocultarPassword = !_ocultarPassword),
                    ),
                  ),
                  validator: validarRequerida,
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
              color: t.colorScheme.errorContainer,
              border: Border.all(color: t.colorScheme.error),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.error_outline,
                  color: t.colorScheme.onErrorContainer,
                  size: 20,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: t.colorScheme.onErrorContainer,
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
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
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.5,
                      color: Colors.white,
                    ),
                  )
                : const Text('Iniciar sesión'),
          ),
        ),
      ],
    ),
  );
}
