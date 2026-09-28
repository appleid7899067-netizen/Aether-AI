import React, { useState } from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import {
  Box,
  IconButton,
  Drawer,
  Tabs,
  Tab,
  Badge,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Chat as ChatIcon,
  Face as FaceIcon,
  Visibility as MonitorIcon,
  Lightbulb as SuggestionsIcon,
  CalendarToday as PlanIcon,
  Computer as ControlIcon,
  BugReport as BugBountyIcon,
  Assessment as ReportIcon,
  EmojiEmotions as PersonalityIcon,
  Security as LiveTestingIcon,
} from '@mui/icons-material';
import { ThemeProvider } from './themes/ThemeContext';
import JarvisDashboard from './components/JarvisDashboard';
import ChatInterface from './components/ChatInterface';
import Settings from './components/Settings';
import Notifications from './components/Notifications';
import CompactTaskBar from './components/CompactTaskBar';
import ThemeSwitcher from './components/ThemeSwitcher';
import SimpleVoiceAssistant from './components/SimpleVoiceAssistant';
import MonitoringPanel from './components/v090/MonitoringPanel';
import ProactiveSuggestions from './components/v090/ProactiveSuggestions';
import DailyPlan from './components/v090/DailyPlan';
import PCControlPanel from './components/v090/PCControlPanel';
import BugBountyAutopilot from './components/v090/BugBountyAutopilot';
import DailyReport from './components/v090/DailyReport';
import PersonalitySettings from './components/v090/PersonalitySettings';
import LiveTestingPanel from './components/v090/LiveTestingPanel';
import TaskQueueDashboard from './components/TaskQueueDashboard';

function App() {
  const [showChat, setShowChat] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showV090Panel, setShowV090Panel] = useState(false);
  const [v090Tab, setV090Tab] = useState(0);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [newSuggestions, setNewSuggestions] = useState(0);
  const [activeTasks, setActiveTasks] = useState([
    { name: 'Voice Recognition', status: 'idle' },
    { name: 'LLM Processing', status: 'idle' },
    { name: 'Memory System', status: 'running' },
  ]);
  const [hudState, setHudState] = useState(null);

  // Listen for HUD updates from Electron backend  
  React.useEffect(() => {
    if (window.electron?.ipcRenderer) {
      const handleStatus = (event, data) => {
        if (data?.type === 'hud_update' || data?.status) {
          setHudState(data);
        }
      };
      window.electron.ipcRenderer.on('aether-status', handleStatus);
      return () => window.electron.ipcRenderer.removeListener('aether-status', handleStatus);
    }
  }, []);

  const handleVoiceCommand = async (command) => {
    console.log('Voice command:', command);
    setIsListening(command === 'start');
    addNotification('Voice detection started', 'info');

    if (command === 'start') {
      setTimeout(() => {
        setIsListening(false);
        setIsSpeaking(true);
        setTimeout(() => setIsSpeaking(false), 2000);
      }, 3000);
    }
  };

  const addNotification = (message, type = 'info') => {
    const newNotification = {
      id: Date.now(),
      message,
      type,
    };
    setNotifications([...notifications, newNotification]);
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== newNotification.id));
    }, 5000);
  };

  const v090Panels = [
    { label: 'Monitor', icon: <MonitorIcon />, component: <MonitoringPanel /> },
    { label: 'Suggestions', icon: <SuggestionsIcon />, component: <ProactiveSuggestions />, badge: newSuggestions },
    { label: 'Daily Plan', icon: <PlanIcon />, component: <DailyPlan /> },
    { label: 'PC Control', icon: <ControlIcon />, component: <PCControlPanel /> },
    { label: 'Bug Bounty', icon: <BugBountyIcon />, component: <BugBountyAutopilot /> },
    { label: 'Live Testing', icon: <LiveTestingIcon />, component: <LiveTestingPanel /> },
    { label: 'Report', icon: <ReportIcon />, component: <DailyReport /> },
    { label: 'Personality', icon: <PersonalityIcon />, component: <PersonalitySettings /> },
  ];

  return (
    <ThemeProvider>
      <CssBaseline />
      <Box sx={{
        width: '100vw',
        height: '100vh',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'transparent'
      }}>

        {/* Compact Rectangular Widget */}
        <Box sx={{
          width: '90%',
          maxWidth: '380px',
          background: 'rgba(10, 15, 25, 0.85)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(0, 255, 255, 0.2)',
          borderRadius: '12px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          WebkitAppRegion: 'drag', // Allow dragging the window from this widget
          pointerEvents: 'auto'
        }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: isListening ? '#ffcc00' : isSpeaking ? '#00ffff' : '#4caf50', boxShadow: '0 0 10px currentColor' }} />
              <div style={{ fontWeight: 'bold', color: '#fff', fontSize: '1.2rem', fontFamily: 'monospace' }}>AETHER AI</div>
            </Box>

            <Box sx={{ display: 'flex', gap: 0.5, WebkitAppRegion: 'no-drag' }}>
              <IconButton size="small" onClick={() => setShowV090Panel(!showV090Panel)} sx={{ color: 'var(--primary-color)' }}>
                <SuggestionsIcon fontSize="small" />
              </IconButton>
              <IconButton size="small" onClick={() => setShowChat(!showChat)} sx={{ color: 'var(--primary-color)' }}>
                <ChatIcon fontSize="small" />
              </IconButton>
              <IconButton size="small" onClick={() => setShowSettings(!showSettings)} sx={{ color: 'var(--primary-color)' }}>
                <SettingsIcon fontSize="small" />
              </IconButton>
            </Box>
          </Box>

          <Box sx={{
            background: 'rgba(0,0,0,0.3)',
            borderRadius: '8px',
            padding: '12px',
            minHeight: '60px',
            display: 'flex',
            alignItems: 'center',
            border: '1px solid rgba(255,255,255,0.05)',
            webkitAppRegion: 'no-drag'
          }}>
            <SimpleVoiceAssistant />
            <div style={{ color: '#ccc', fontStyle: 'italic', fontSize: '0.9rem', width: '100%', textAlign: 'center' }}>
              {isListening ? "Listening, Sir..." : isSpeaking ? "Speaking..." : "Awaiting Systems..."}
            </div>
          </Box>
        </Box>

        <Drawer
          anchor="left"
          open={showV090Panel}
          onClose={() => setShowV090Panel(false)}
          PaperProps={{
            sx: {
              width: { xs: '100%', sm: 500, md: 600 },
              backgroundColor: 'rgba(0, 10, 20, 0.95)',
              backdropFilter: 'blur(10px)',
              borderRight: '1px solid rgba(156, 39, 176, 0.3)',
            },
          }}
        >
          <Box sx={{ p: 2 }}>
            <Tabs
              value={v090Tab}
              onChange={(e, newValue) => setV090Tab(newValue)}
              variant="scrollable"
              scrollButtons="auto"
              sx={{
                mb: 2,
                '& .MuiTab-root': {
                  color: 'rgba(255, 255, 255, 0.6)',
                  minWidth: 'auto',
                  px: 2,
                },
                '& .Mui-selected': {
                  color: '#9c27b0',
                },
                '& .MuiTabs-indicator': {
                  backgroundColor: '#9c27b0',
                  boxShadow: '0 0 10px #743380ff',
                },
              }}
            >
              {v090Panels.map((panel, index) => (
                <Tab
                  key={index}
                  icon={
                    panel.badge ? (
                      <Badge badgeContent={panel.badge} color="error">
                        {panel.icon}
                      </Badge>
                    ) : (
                      panel.icon
                    )
                  }
                  label={panel.label}
                  iconPosition="start"
                />
              ))}
            </Tabs>
            <Box sx={{ maxHeight: 'calc(100vh - 120px)', overflow: 'auto' }}>
              {v090Panels[v090Tab]?.component}
            </Box>
          </Box>
        </Drawer>

        <Drawer
          anchor="right"
          open={showChat}
          onClose={() => setShowChat(false)}
          PaperProps={{
            sx: {
              width: { xs: '100%', sm: 400 },
              backgroundColor: 'rgba(7, 40, 40, 0.95)',
              backdropFilter: 'blur(10px)',
              borderLeft: '1px solid rgba(9, 237, 237, 0.3)',
            },
          }}
        >
          <ChatInterface sessionId="voice-session" onClose={() => setShowChat(false)} />
        </Drawer>
        {/* Desktop Character and Floating Bubble removed - using SimpleVoiceAssistant instead */}

        {/* Settings drawer + notifications + task queue overlay */}
        <Drawer anchor="right" open={showSettings} onClose={() => setShowSettings(false)}>
          <Settings />
        </Drawer>
        <Notifications notifications={notifications} />
        <CompactTaskBar tasks={activeTasks} hudState={hudState} />
      </Box>
    </ThemeProvider>
  );
}

export default App;
