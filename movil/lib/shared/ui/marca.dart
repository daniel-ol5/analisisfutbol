import 'package:flutter/material.dart';

import '../../app/tema.dart';

class SelloArea extends StatelessWidget {
  const SelloArea({super.key});

  @override
  Widget build(BuildContext context) => const DecoratedBox(
    decoration: BoxDecoration(
      color: limaMarca,
      borderRadius: BorderRadius.all(Radius.circular(10)),
    ),
    child: SizedBox.square(
      dimension: 42,
      child: Icon(Icons.stadium_outlined, color: menuOscuro, size: 23),
    ),
  );
}
