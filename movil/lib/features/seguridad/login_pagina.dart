/// CU-02 · Iniciar sesión.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../shared/api/cliente.dart';
import 'api.dart';
import 'validacion.dart';
import 'widgets/aviso.dart';

class LoginPagina extends StatefulWidget {
  const LoginPagina({super.key, this.destino = '/perfil'});

  /// Ruta a la que se vuelve después de iniciar sesión.
  final String destino;

  @override
  State<LoginPagina> createState() => _LoginPaginaState();
}

class _LoginPaginaState extends State<LoginPagina> {
  final _formulario = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _enviando = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _ingresar() async {
    if (!_formulario.currentState!.validate()) return;
    setState(() {
      _enviando = true;
      _error = null;
    });
    try {
      // El backend no normaliza el email: se hace acá, igual que en la web.
      await iniciarSesion(_email.text.trim().toLowerCase(), _password.text);
      if (mounted) context.go(widget.destino);
    } on ErrorApi catch (e) {
      setState(() => _error = switch (e.codigo) {
            401 => 'Correo o contraseña incorrectos.',
            403 => 'La cuenta está desactivada.',
            _ => e.detalle,
          });
    } catch (_) {
      setState(() => _error = 'Sin conexión con el servidor. Intenta de nuevo.');
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Iniciar sesión'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Volver al inicio',
          onPressed: () => context.go('/'),
        ),
      ),
      body: SafeArea(
        child: Form(
          key: _formulario,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
            children: [
              Text('Área Técnica', style: t.textTheme.titleLarge),
              const SizedBox(height: 20),
              if (_error != null) ...[
                Aviso(texto: _error!),
                const SizedBox(height: 16),
              ],
              TextFormField(
                controller: _email,
                decoration: const InputDecoration(labelText: 'Correo electrónico'),
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                textInputAction: TextInputAction.next,
                validator: validarEmail,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _password,
                decoration: const InputDecoration(labelText: 'Contraseña'),
                obscureText: true,
                autofillHints: const [AutofillHints.password],
                onFieldSubmitted: (_) => _ingresar(),
                validator: validarRequerida,
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: _enviando ? null : _ingresar,
                child: Text(_enviando ? 'Ingresando…' : 'Ingresar'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
