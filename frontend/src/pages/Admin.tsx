import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, Trash2, Play, Save, Eye, EyeOff, Upload } from "lucide-react";
import UserMenu from "@/components/UserMenu";

const Admin = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");

  // Mock data for files
  const files = Array.from({ length: 150 }, (_, i) => ({
    id: i + 1,
    name: `Document_${i + 1}.pdf`,
    type: i % 3 === 0 ? "PDF" : i % 3 === 1 ? "DOC" : "DOCX",
    size: `${Math.floor(Math.random() * 5000) + 100}KB`,
    uploadDate: new Date(2024, Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1).toLocaleDateString(),
  }));

  // Mock data for generated files
  const generatedFiles = [
    { id: 1, name: "Mindfulness_Meditation_Guide.mp3", type: "Audio", size: "2.3MB", createdDate: "2024-01-15" },
    { id: 2, name: "Breathing_Exercise_Video.mp4", type: "Video", size: "15.7MB", createdDate: "2024-01-14" },
    { id: 3, name: "Sleep_Story_Audio.mp3", type: "Audio", size: "4.1MB", createdDate: "2024-01-13" },
    { id: 4, name: "Yoga_Session_Guide.mp4", type: "Video", size: "22.4MB", createdDate: "2024-01-12" },
    { id: 5, name: "Relaxation_Sounds.mp3", type: "Audio", size: "3.8MB", createdDate: "2024-01-11" },
  ];

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (username === "admin" && password === "admin") {
      setIsAuthenticated(true);
      setLoginError("");
    } else {
      setLoginError("Invalid username or password");
    }
  };

  const handleSaveApiKey = async () => {
    setIsSaving(true);
    setSaveMessage("");

    try {
      // Simulate API call to save the API key
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Here you would typically make an API call to save the key
      // await saveApiKey(apiKey);

      setSaveMessage("API Key saved successfully!");
      setTimeout(() => setSaveMessage(""), 3000);
    } catch (error) {
      setSaveMessage("Failed to save API Key. Please try again.");
      setTimeout(() => setSaveMessage(""), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  const handleFileUpload = () => {
    // Create a file input element
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.pdf,.doc,.docx,.txt';
    fileInput.multiple = true;

    fileInput.onchange = (e) => {
      const target = e.target as HTMLInputElement;
      if (target.files) {
        console.log('Files selected:', target.files);
        // Here you would typically upload the files to your server
        // For now, we'll just log the selected files
        Array.from(target.files).forEach(file => {
          console.log(`Uploading: ${file.name} (${file.size} bytes)`);
        });
      }
    };

    fileInput.click();
  };

  const handleFileOperation = (fileId: number, operation: string) => {
    console.log(`${operation} file with ID: ${fileId}`);
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-2xl text-center">Admin Login</CardTitle>
            <CardDescription className="text-center">Enter your credentials to access the admin panel</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              {loginError && (
                <p className="text-sm text-red-600">{loginError}</p>
              )}
              <Button type="submit" className="w-full">
                Login
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto py-8 px-4">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Admin Panel</h1>
          <UserMenu />
        </div>

        <div className="space-y-8">
          {/* API Key Configuration Section */}
          <Card>
            <CardHeader>
              <CardTitle>API Key Configuration</CardTitle>
              <CardDescription>Update your API key for language model access</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="apiKey">API Key</Label>
                  <div className="relative">
                    <Input
                      id="apiKey"
                      type={showApiKey ? "text" : "password"}
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="Enter your API key here..."
                      className="pr-10"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                      onClick={() => setShowApiKey(!showApiKey)}
                    >
                      {showApiKey ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                  <p className="text-sm text-gray-500">
                    Your API key is encrypted and stored securely. Never share your API key publicly.
                  </p>
                </div>

                <div className="flex items-center gap-4">
                  <Button
                    onClick={handleSaveApiKey}
                    disabled={!apiKey.trim() || isSaving}
                    className="flex items-center gap-2"
                  >
                    <Save className="w-4 h-4" />
                    {isSaving ? "Saving..." : "Save API Key"}
                  </Button>

                  {saveMessage && (
                    <p className={`text-sm ${saveMessage.includes("successfully") ? "text-green-600" : "text-red-600"}`}>
                      {saveMessage}
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Files Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Files
                <Button
                  onClick={handleFileUpload}
                  className="ml-auto flex items-center gap-2"
                  size="sm"
                >
                  <Upload className="w-4 h-4" />
                  Upload Files
                </Button>
              </CardTitle>
              <CardDescription>Manage uploaded PDF and document files</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-96">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead>Upload Date</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {files.map((file) => (
                      <TableRow key={file.id}>
                        <TableCell className="flex items-center gap-2">
                          <FileText className="w-4 h-4" />
                          {file.name}
                        </TableCell>
                        <TableCell>{file.type}</TableCell>
                        <TableCell>{file.size}</TableCell>
                        <TableCell>{file.uploadDate}</TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleFileOperation(file.id, "delete")}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Generated Files Section */}
          <Card>
            <CardHeader>
              <CardTitle>Generated Files</CardTitle>
              <CardDescription>Audio and video files created by the meditation guide generator</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {generatedFiles.map((file) => (
                  <div key={file.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center gap-3">
                      {file.type === "Audio" ? (
                        <div className="p-2 bg-blue-100 rounded">
                          <Play className="w-4 h-4 text-blue-600" />
                        </div>
                      ) : (
                        <div className="p-2 bg-green-100 rounded">
                          <Play className="w-4 h-4 text-green-600" />
                        </div>
                      )}
                      <div>
                        <h3 className="font-medium">{file.name}</h3>
                        <p className="text-sm text-gray-500">{file.type} • {file.size} • Created {file.createdDate}</p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Admin;
