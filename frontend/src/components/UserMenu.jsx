import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { LogOut, User, FolderKanban, Sparkles, Calendar } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return '—';
  }
}

function initials(name) {
  if (!name) return 'U';
  return name
    .split(' ')
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export default function UserMenu({ user, onLogout }) {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    let mounted = true;
    axios
      .get(`${API}/user/stats`, { withCredentials: true })
      .then((r) => {
        if (mounted) setStats(r.data);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          data-testid="user-menu-trigger"
          className="flex items-center gap-2 px-2 py-1.5 rounded-sm hover:bg-white/5 transition-colors group"
        >
          <Avatar className="w-8 h-8 ring-2 ring-[#E4FF00]/40 group-hover:ring-[#E4FF00] transition-all">
            <AvatarImage src={user?.picture} alt={user?.name} />
            <AvatarFallback className="bg-[#E4FF00] text-[#050505] font-['Chivo'] font-black text-xs">
              {initials(user?.name)}
            </AvatarFallback>
          </Avatar>
          <span className="text-sm font-['IBM_Plex_Sans'] text-white max-w-[120px] truncate hidden sm:inline">
            {user?.name || user?.email || 'Utilisateur'}
          </span>
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        data-testid="user-menu-content"
        className="w-72 bg-white/[0.04] border-white/10 backdrop-blur-xl text-white"
      >
        <DropdownMenuLabel className="px-3 py-3">
          <div className="flex items-center gap-3">
            <Avatar className="w-10 h-10">
              <AvatarImage src={user?.picture} alt={user?.name} />
              <AvatarFallback className="bg-[#E4FF00] text-[#050505] font-['Chivo'] font-black">
                {initials(user?.name)}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <div className="font-['Chivo'] font-bold text-white truncate">
                {user?.name || 'Utilisateur'}
              </div>
              <div className="text-xs text-[#A1A1AA] truncate font-['IBM_Plex_Mono']">
                {user?.email || user?.phone_number || ''}
              </div>
            </div>
          </div>
        </DropdownMenuLabel>

        <DropdownMenuSeparator className="bg-white/10" />

        {/* Stats */}
        <div className="px-3 py-2 space-y-2 text-sm font-['IBM_Plex_Sans']">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-[#A1A1AA]">
              <FolderKanban className="w-4 h-4" /> Projets
            </span>
            <span data-testid="stats-project-count" className="font-['Chivo'] font-bold text-[#E4FF00]">
              {stats?.project_count ?? '…'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-[#A1A1AA]">
              <Sparkles className="w-4 h-4" /> Plan
            </span>
            <span data-testid="stats-plan" className="font-['Chivo'] font-bold text-[#00FF66]">
              {stats?.plan ?? 'Gratuit'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-[#A1A1AA]">
              <Calendar className="w-4 h-4" /> Dernier login
            </span>
            <span data-testid="stats-last-login" className="font-['IBM_Plex_Mono'] text-xs text-white/80">
              {formatDate(stats?.last_login)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-[#A1A1AA]">
              <User className="w-4 h-4" /> Membre depuis
            </span>
            <span className="font-['IBM_Plex_Mono'] text-xs text-white/80">
              {formatDate(stats?.member_since)}
            </span>
          </div>
        </div>

        <DropdownMenuSeparator className="bg-white/10" />

        <DropdownMenuItem
          onClick={onLogout}
          data-testid="user-menu-logout"
          className="px-3 py-2 cursor-pointer text-red-400 hover:!bg-red-500/10 hover:!text-red-400 focus:bg-red-500/10 focus:text-red-400"
        >
          <LogOut className="w-4 h-4 mr-2" />
          Déconnexion
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
