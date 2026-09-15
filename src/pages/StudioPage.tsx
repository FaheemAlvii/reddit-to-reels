import { useState } from "react";
import { motion } from "framer-motion";
import {
  Bot, PenLine, Link as LinkIcon, Play, Loader2, Film, Scissors, Mic, MicOff,
  BookOpen, MessageSquare, Gamepad2, Flame, HandMetal, HelpCircle, Star, Brain, Plus, Trash2, ArrowRight
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import { PipelinePanel } from "@/components/PipelinePanel";

const CONTENT_STYLES = [
  { id: "story", label: "Story", icon: BookOpen, desc: "First-person confessional / narrative", color: "text-blue-400" },
  { id: "qa", label: "Q&A", icon: MessageSquare, desc: "Viral AskReddit style thread with answers", color: "text-green-400" },
  { id: "interactive", label: "Interactive", icon: Gamepad2, desc: '"Put a finger down" / quizzes with pauses', color: "text-purple-400" },
  { id: "hot_take", label: "Hot Take", icon: Flame, desc: "Controversial opinion driving comments", color: "text-orange-400" },
];

const NICHES = [
  { id: "relationship_drama", name: "Relationship Drama", emoji: "💔" },
  { id: "childhood_nostalgia", name: "Childhood Nostalgia", emoji: "🧸" },
  { id: "workplace_horror", name: "Workplace Horror", emoji: "💼" },
  { id: "dating_disasters", name: "Dating Disasters", emoji: "🫠" },
  { id: "family_secrets", name: "Family Secrets", emoji: "🤫" },
  { id: "school_memories", name: "School Memories", emoji: "🎒" },
  { id: "paranormal_encounters", name: "Paranormal", emoji: "👻" },
  { id: "neighbor_stories", name: "Neighbor Stories", emoji: "🏠" },
  { id: "travel_nightmares", name: "Travel Nightmares", emoji: "✈️" },
  { id: "food_culture", name: "Food & Culture", emoji: "🍕" },
];

const INTERACTIVE_FORMATS = [
  { id: "put_a_finger_down", label: "Put a Finger Down", icon: HandMetal },
  { id: "would_you_rather", label: "Would You Rather", icon: HelpCircle },
  { id: "rate_yourself", label: "Rate Yourself", icon: Star },
  { id: "guess_the_answer", label: "Guess the Answer", icon: Brain },
];

const VIDEO_MODES = [
  { id: "short_reel", label: "Short Reel", icon: Scissors, desc: "< 60s vertical video" },
  { id: "reel", label: "Standard Reel", icon: Film, desc: "60-90s vertical format" },
  { id: "full_video", label: "Full Video", icon: Film, desc: "Full-length horizontal" },
];

interface QaComment {
  author: string;
  body: string;
}

export default function StudioPage() {
  const [activeTab, setActiveTab] = useState("ai");
  const { toast } = useToast();
  const qc = useQueryClient();

  // AI Generator State
  const [aiStyle, setAiStyle] = useState("story");
  const [aiNiche, setAiNiche] = useState("relationship_drama");
  const [aiTopic, setAiTopic] = useState("");
  const [aiInteractiveFormat, setAiInteractiveFormat] = useState("put_a_finger_down");
  const [aiVideoMode, setAiVideoMode] = useState("short_reel");
  const [aiTtsEnabled, setAiTtsEnabled] = useState(true);
  const [aiSubmitting, setAiSubmitting] = useState(false);

  // Manual Script State
  const [manualFormatMode, setManualFormatMode] = useState("story");
  const [manualTitle, setManualTitle] = useState("");
  const [manualContent, setManualContent] = useState("");
  const [manualComments, setManualComments] = useState<QaComment[]>([{ author: "", body: "" }]);
  const [manualVideoMode, setManualVideoMode] = useState("short_reel");
  const [manualTtsEnabled, setManualTtsEnabled] = useState(true);
  const [manualSubmitting, setManualSubmitting] = useState(false);

  // URL Import State
  const [urlInput, setUrlInput] = useState("");
  const [urlVideoMode, setUrlVideoMode] = useState("short_reel");
  const [urlFormatMode, setUrlFormatMode] = useState("story");
  const [urlSubmitting, setUrlSubmitting] = useState(false);

  // Manual comments helper
  const addComment = () => setManualComments((prev) => [...prev, { author: "", body: "" }]);
  const removeComment = (i: number) => setManualComments((prev) => prev.filter((_, idx) => idx !== i));
  const updateComment = (i: number, field: keyof QaComment, value: string) =>
    setManualComments((prev) => prev.map((c, idx) => (idx === i ? { ...c, [field]: value } : c)));

  // Submit AI Generation
  const handleAiSubmit = async () => {
    setAiSubmitting(true);
    try {
      await api.runPipelineAI({
        content_style: aiStyle,
        niche: aiNiche,
        custom_topic: aiTopic || undefined,
        interactive_format: aiStyle === "interactive" ? aiInteractiveFormat : undefined,
        video_mode: aiVideoMode,
        tts_enabled: aiTtsEnabled,
      });
      toast({ title: "AI Pipeline Started", description: "Generating original content and rendering Reel..." });
      qc.invalidateQueries({ queryKey: ["pipeline"] });
    } catch (e: any) {
      toast({ title: "Generation Failed", description: e.message, variant: "destructive" });
    } finally {
      setAiSubmitting(false);
    }
  };

  // Submit Manual Custom Script
  const handleManualSubmit = async () => {
    if (!manualTitle.trim() || !manualContent.trim()) {
      toast({ title: "Missing Fields", description: "Please enter a title and content.", variant: "destructive" });
      return;
    }
    setManualSubmitting(true);
    try {
      const params: Parameters<typeof api.runPipelineCustom>[0] = {
        title: manualTitle,
        content: manualContent,
        format_mode: manualFormatMode,
        video_mode: manualVideoMode,
        tts_enabled: manualTtsEnabled,
      };
      if (manualFormatMode === "qa") {
        params.comments = manualComments
          .filter((c) => c.body.trim())
          .map((c) => ({ author: c.author.trim() || "Anonymous", body: c.body.trim() }));
      }
      await api.runPipelineCustom(params);
      toast({ title: "Custom Script Pipeline Started", description: "Converting script into Reel..." });
      qc.invalidateQueries({ queryKey: ["pipeline"] });
    } catch (e: any) {
      toast({ title: "Generation Failed", description: e.message, variant: "destructive" });
    } finally {
      setManualSubmitting(false);
    }
  };

  // Submit URL Import
  const handleUrlSubmit = async () => {
    if (!urlInput.trim()) {
      toast({ title: "Missing URL", description: "Please enter a post or story URL.", variant: "destructive" });
      return;
    }
    setUrlSubmitting(true);
    try {
      await api.runPipelineFromUrl({
        url: urlInput.trim(),
        video_mode: urlVideoMode,
        format_mode: urlFormatMode,
      });
      toast({ title: "URL Pipeline Started", description: "Fetching content and generating Reel..." });
      qc.invalidateQueries({ queryKey: ["pipeline"] });
    } catch (e: any) {
      toast({ title: "Import Failed", description: e.message, variant: "destructive" });
    } finally {
      setUrlSubmitting(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      {/* Studio Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Story Studio</h1>
            <Badge variant="default" className="glow-primary text-[10px] px-2 py-0.5">
              Primary Workflow
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Create high-engagement vertical Reels from AI generated scripts, manual stories, or web text.
          </p>
        </div>
      </div>

      {/* Main Studio Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Creation Workspace (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid grid-cols-3 w-full bg-secondary/60 p-1 rounded-xl">
              <TabsTrigger value="ai" className="gap-2 text-xs font-medium rounded-lg">
                <Bot className="h-3.5 w-3.5 text-accent" />
                AI Story Generator
              </TabsTrigger>
              <TabsTrigger value="manual" className="gap-2 text-xs font-medium rounded-lg">
                <PenLine className="h-3.5 w-3.5 text-primary" />
                Manual Script Writer
              </TabsTrigger>
              <TabsTrigger value="url" className="gap-2 text-xs font-medium rounded-lg">
                <LinkIcon className="h-3.5 w-3.5 text-blue-400" />
                URL / Text Import
              </TabsTrigger>
            </TabsList>

            {/* TAB 1: AI STORY GENERATOR */}
            <TabsContent value="ai" className="mt-4 space-y-5">
              <Card className="border-border bg-card shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Bot className="h-4 w-4 text-accent" />
                    Generate AI Story Reel
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Choose a story style, niche, and prompt to produce a fresh viral script.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  {/* Style selector */}
                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wider text-muted-foreground">Content Style</Label>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {CONTENT_STYLES.map((s) => (
                        <button
                          key={s.id}
                          type="button"
                          onClick={() => setAiStyle(s.id)}
                          className={cn(
                            "flex items-start gap-3 p-3 rounded-lg border text-left transition-all",
                            aiStyle === s.id
                              ? "border-accent bg-accent/10 text-foreground ring-1 ring-accent/30"
                              : "border-border bg-secondary/40 text-muted-foreground hover:border-accent/30"
                          )}
                        >
                          <s.icon className={cn("h-5 w-5 shrink-0 mt-0.5", s.color)} />
                          <div>
                            <p className="text-xs font-semibold">{s.label}</p>
                            <p className="text-[10px] opacity-70 leading-normal">{s.desc}</p>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Niche grid */}
                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wider text-muted-foreground">Niche Category</Label>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                      {NICHES.map((n) => (
                        <button
                          key={n.id}
                          type="button"
                          onClick={() => setAiNiche(n.id)}
                          className={cn(
                            "flex items-center gap-2 p-2 rounded-lg border text-left transition-all text-xs",
                            aiNiche === n.id
                              ? "border-primary bg-primary/10 text-foreground font-medium"
                              : "border-border bg-secondary/30 text-muted-foreground hover:border-primary/30"
                          )}
                        >
                          <span className="text-base">{n.emoji}</span>
                          <span className="truncate text-[11px]">{n.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Interactive format if style is interactive */}
                  {aiStyle === "interactive" && (
                    <div className="space-y-2 pt-1 border-t border-border/60">
                      <Label className="text-xs uppercase tracking-wider text-muted-foreground">Interactive Challenge Format</Label>
                      <div className="grid grid-cols-2 gap-2">
                        {INTERACTIVE_FORMATS.map((f) => (
                          <button
                            key={f.id}
                            type="button"
                            onClick={() => setAiInteractiveFormat(f.id)}
                            className={cn(
                              "flex items-center gap-2 p-2.5 rounded-lg border text-xs text-left transition-all",
                              aiInteractiveFormat === f.id
                                ? "border-purple-500 bg-purple-500/10 text-foreground font-medium"
                                : "border-border bg-secondary/30 text-muted-foreground hover:border-purple-500/30"
                            )}
                          >
                            <f.icon className="h-4 w-4 shrink-0 text-purple-400" />
                            <span>{f.label}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Custom Topic */}
                  <div className="space-y-1.5 pt-1">
                    <Label className="text-xs text-muted-foreground">Custom Story Topic / Hook Prompt (Optional)</Label>
                    <Input
                      value={aiTopic}
                      onChange={(e) => setAiTopic(e.target.value)}
                      placeholder="e.g., 'Found out my roommate has been living in the attic for 3 months'"
                      className="h-9 text-xs bg-secondary border-border"
                    />
                    <p className="text-[10px] text-muted-foreground">Leave blank to let AI select an original trending hook.</p>
                  </div>

                  {/* Video format & TTS */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-border">
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">Video Mode</Label>
                      <div className="flex gap-1.5">
                        {VIDEO_MODES.map((m) => (
                          <Button
                            key={m.id}
                            type="button"
                            size="sm"
                            variant={aiVideoMode === m.id ? "default" : "outline"}
                            onClick={() => setAiVideoMode(m.id)}
                            className="flex-1 text-[11px] h-8 px-2"
                          >
                            {m.label}
                          </Button>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">Voiceover Narration</Label>
                      <Button
                        type="button"
                        variant={aiTtsEnabled ? "outline" : "ghost"}
                        onClick={() => setAiTtsEnabled(!aiTtsEnabled)}
                        className="w-full h-8 text-xs justify-between"
                      >
                        <span className="flex items-center gap-1.5">
                          {aiTtsEnabled ? <Mic className="h-3.5 w-3.5 text-primary" /> : <MicOff className="h-3.5 w-3.5 text-muted-foreground" />}
                          Text-to-Speech
                        </span>
                        <Badge variant={aiTtsEnabled ? "default" : "secondary"} className="text-[9px]">
                          {aiTtsEnabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </Button>
                    </div>
                  </div>

                  {/* Submit Action */}
                  <Button
                    onClick={handleAiSubmit}
                    disabled={aiSubmitting}
                    className="w-full h-11 font-semibold text-sm glow-accent gap-2 mt-2"
                  >
                    {aiSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
                    Generate AI Reel
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* TAB 2: MANUAL SCRIPT WRITER */}
            <TabsContent value="manual" className="mt-4 space-y-5">
              <Card className="border-border bg-card shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <PenLine className="h-4 w-4 text-primary" />
                    Write Custom Script / Story
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Compose your own story, confessional, or Q&A thread directly.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  {/* Mode switch */}
                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wider text-muted-foreground">Format Mode</Label>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setManualFormatMode("story")}
                        className={cn(
                          "flex items-center justify-center gap-2 p-2.5 rounded-lg border text-xs font-medium transition-all",
                          manualFormatMode === "story"
                            ? "border-primary bg-primary/10 text-foreground"
                            : "border-border bg-secondary/40 text-muted-foreground hover:border-primary/30"
                        )}
                      >
                        <BookOpen className="h-4 w-4" />
                        Story Mode (Narrated text)
                      </button>
                      <button
                        type="button"
                        onClick={() => setManualFormatMode("qa")}
                        className={cn(
                          "flex items-center justify-center gap-2 p-2.5 rounded-lg border text-xs font-medium transition-all",
                          manualFormatMode === "qa"
                            ? "border-primary bg-primary/10 text-foreground"
                            : "border-border bg-secondary/40 text-muted-foreground hover:border-primary/30"
                        )}
                      >
                        <MessageSquare className="h-4 w-4" />
                        Q&A Mode (Question & Speaker Answers)
                      </button>
                    </div>
                  </div>

                  {/* Title & Body */}
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Reel Title / Hook Header</Label>
                    <Input
                      value={manualTitle}
                      onChange={(e) => setManualTitle(e.target.value)}
                      placeholder={manualFormatMode === "qa" ? "What's the weirdest thing a stranger ever said to you?" : "My neighbor's 3AM secret"}
                      className="h-9 text-xs bg-secondary border-border"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <Label className="text-xs text-muted-foreground">
                        {manualFormatMode === "qa" ? "Main Question / Context" : "Story Content Script"}
                      </Label>
                      <span className="text-[10px] text-muted-foreground">{manualContent.length} chars</span>
                    </div>
                    <Textarea
                      value={manualContent}
                      onChange={(e) => setManualContent(e.target.value)}
                      placeholder={
                        manualFormatMode === "qa"
                          ? "Enter the main question or context here..."
                          : "Write or paste your full story script here. Paragraphs will be narrated in sequence."
                      }
                      className="min-h-[140px] text-xs bg-secondary border-border resize-none leading-relaxed"
                    />
                  </div>

                  {/* Q&A comment responses */}
                  {manualFormatMode === "qa" && (
                    <div className="space-y-3 pt-2 border-t border-border">
                      <div className="flex items-center justify-between">
                        <Label className="text-xs text-muted-foreground">Speaker Answers / Comments</Label>
                        <Button type="button" variant="outline" size="sm" onClick={addComment} className="h-7 text-xs gap-1">
                          <Plus className="h-3 w-3" /> Add Speaker
                        </Button>
                      </div>
                      <ScrollArea className="max-h-[220px]">
                        <div className="space-y-2 pr-2">
                          {manualComments.map((c, i) => (
                            <div key={i} className="flex gap-2 items-start p-2.5 rounded-lg border border-border/60 bg-secondary/20">
                              <div className="flex-1 space-y-1.5">
                                <Input
                                  value={c.author}
                                  onChange={(e) => updateComment(i, "author", e.target.value)}
                                  placeholder={`Speaker ${i + 1} Name (e.g. u/Throwaway123)`}
                                  className="h-7 text-xs bg-secondary border-border"
                                />
                                <Textarea
                                  value={c.body}
                                  onChange={(e) => updateComment(i, "body", e.target.value)}
                                  placeholder="Speaker answer text..."
                                  className="min-h-[60px] text-xs bg-secondary border-border resize-none"
                                />
                              </div>
                              {manualComments.length > 1 && (
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => removeComment(i)}
                                  className="h-7 w-7 p-0 text-destructive hover:bg-destructive/10"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              )}
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    </div>
                  )}

                  {/* Format & TTS */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-border">
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">Video Mode</Label>
                      <div className="flex gap-1.5">
                        {VIDEO_MODES.map((m) => (
                          <Button
                            key={m.id}
                            type="button"
                            size="sm"
                            variant={manualVideoMode === m.id ? "default" : "outline"}
                            onClick={() => setManualVideoMode(m.id)}
                            className="flex-1 text-[11px] h-8 px-2"
                          >
                            {m.label}
                          </Button>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">Voiceover Narration</Label>
                      <Button
                        type="button"
                        variant={manualTtsEnabled ? "outline" : "ghost"}
                        onClick={() => setManualTtsEnabled(!manualTtsEnabled)}
                        className="w-full h-8 text-xs justify-between"
                      >
                        <span className="flex items-center gap-1.5">
                          {manualTtsEnabled ? <Mic className="h-3.5 w-3.5 text-primary" /> : <MicOff className="h-3.5 w-3.5 text-muted-foreground" />}
                          Text-to-Speech
                        </span>
                        <Badge variant={manualTtsEnabled ? "default" : "secondary"} className="text-[9px]">
                          {manualTtsEnabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </Button>
                    </div>
                  </div>

                  {/* Submit Action */}
                  <Button
                    onClick={handleManualSubmit}
                    disabled={manualSubmitting}
                    className="w-full h-11 font-semibold text-sm glow-primary gap-2 mt-2"
                  >
                    {manualSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                    Generate Custom Script Reel
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* TAB 3: URL IMPORT */}
            <TabsContent value="url" className="mt-4 space-y-5">
              <Card className="border-border bg-card shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <LinkIcon className="h-4 w-4 text-blue-400" />
                    Import from Web / URL
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Paste an article or post URL to convert into a short video Reel.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Source URL</Label>
                    <Input
                      value={urlInput}
                      onChange={(e) => setUrlInput(e.target.value)}
                      placeholder="https://..."
                      className="h-10 text-xs bg-secondary border-border"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">Format Mode</Label>
                      <div className="flex gap-1.5">
                        <Button
                          type="button"
                          size="sm"
                          variant={urlFormatMode === "story" ? "default" : "outline"}
                          onClick={() => setUrlFormatMode("story")}
                          className="flex-1 text-[11px] h-8"
                        >
                          Story
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant={urlFormatMode === "qa" ? "default" : "outline"}
                          onClick={() => setUrlFormatMode("qa")}
                          className="flex-1 text-[11px] h-8"
                        >
                          Q&A
                        </Button>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">Video Mode</Label>
                      <div className="flex gap-1.5">
                        {VIDEO_MODES.map((m) => (
                          <Button
                            key={m.id}
                            type="button"
                            size="sm"
                            variant={urlVideoMode === m.id ? "default" : "outline"}
                            onClick={() => setUrlVideoMode(m.id)}
                            className="flex-1 text-[11px] h-8 px-2"
                          >
                            {m.label}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </div>

                  <Button
                    onClick={handleUrlSubmit}
                    disabled={urlSubmitting}
                    className="w-full h-11 font-semibold text-sm gap-2 bg-blue-600 hover:bg-blue-700 text-white mt-2"
                  >
                    {urlSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                    Import & Render Reel
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right Side: Live Execution Status (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          <PipelinePanel />
        </div>
      </div>
    </motion.div>
  );
}
