import 'package:flutter/material.dart';

import '../../shared/ui/lista_consultable.dart';
import '../deportivo/agenda/selector_partido.dart';
import 'api.dart';
import 'recomendaciones_pagina.dart';

class AsistenciaPagina extends StatelessWidget {
  const AsistenciaPagina({super.key});

  @override
  Widget build(BuildContext context) => DefaultTabController(
    length: 2,
    child: Scaffold(
      appBar: AppBar(
        title: const Text('Asistencia y reportes'),
        bottom: const TabBar(
          tabs: [
            Tab(text: 'Recomendaciones'),
            Tab(text: 'Reglas'),
          ],
        ),
      ),
      body: TabBarView(
        children: [
          SelectorPartido(
            contenido: (partido) =>
                RecomendacionesPagina(partidoId: partido.id, integrada: true),
          ),
          ListaConsultable<Regla>(
            consultar: listarReglas,
            vacio: 'Todavía no hay reglas tácticas disponibles.',
            tarjeta: (_, regla) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                leading: Icon(
                  regla.activa
                      ? Icons.check_circle_outline
                      : Icons.info_outline,
                ),
                title: Text(regla.nombre),
                subtitle: Text(regla.activa ? 'Activa' : 'Inactiva'),
              ),
            ),
          ),
        ],
      ),
    ),
  );
}
