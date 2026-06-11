/**
 * iter92 — Composant wrapper qui affiche le nom d'un projet/chat traduit
 * automatiquement dans la langue UI courante.
 *
 * Utilisation :
 *   <TranslatedProjectName project={project} className="text-white" />
 */
import React from 'react';
import { useTranslatedProjectName } from '../hooks/useTranslatedProjectName';

export default function TranslatedProjectName({ project, className = '', ...rest }) {
  const name = useTranslatedProjectName(project);
  return <span className={className} {...rest}>{name}</span>;
}
