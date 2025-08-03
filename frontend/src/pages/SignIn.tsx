import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Smartphone, MessageSquare } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import RegisterModal from "@/components/RegisterModal";

const SignIn = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { login, register, isAuthenticated, isLoading: isAuthLoading } = useAuth();
    const [step, setStep] = useState<"phone" | "otp">("phone");
    const [countryCode, setCountryCode] = useState("1");
    const [phoneNumber, setPhoneNumber] = useState("");
    const [otp, setOtp] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [showRegisterModal, setShowRegisterModal] = useState(false);

    // Get the page user was trying to access before being redirected to sign in
    const from = location.state?.from?.pathname || "/";

    // Redirect if user is already authenticated
    useEffect(() => {
        if (isAuthenticated && !isAuthLoading) {
            navigate(from, { replace: true });
        }
    }, [isAuthenticated, isAuthLoading, navigate, from]);

    const formatPhoneNumber = () => {
        return `+${countryCode}-${phoneNumber}`;
    };

    const handlePhoneSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!countryCode.trim()) {
            setError("Please enter country code");
            return;
        }

        if (!phoneNumber.trim()) {
            setError("Please enter your mobile number");
            return;
        }

        setIsSubmitting(true);

        try {
            const formattedPhoneNumber = formatPhoneNumber();

            // Call login API to send OTP
            const response = await login(formattedPhoneNumber);

            // If we get a success response, move to OTP step
            if ('success' in response && response.success) {
                setStep("otp");
            }
        } catch (err: any) {
            setError(err.message || "Failed to send OTP. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleOtpSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!otp.trim()) {
            setError("Please enter the OTP");
            return;
        }

        if (otp.length !== 6) {
            setError("OTP must be 6 digits");
            return;
        }

        setIsSubmitting(true);

        try {
            const formattedPhoneNumber = formatPhoneNumber();

            // Call login API with OTP to verify
            const response = await login(formattedPhoneNumber, otp);

            // If we get an auth response with tokens, redirect to intended page
            if ('access_token' in response) {
                navigate(from, { replace: true });
            }
        } catch (err: any) {
            setError(err.message || "Invalid OTP. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleResendOtp = async () => {
        setError("");
        setIsSubmitting(true);

        try {
            const formattedPhoneNumber = formatPhoneNumber();

            // Call login API again to resend OTP
            await login(formattedPhoneNumber);
        } catch (err: any) {
            setError(err.message || "Failed to resend OTP. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleRegister = () => {
        setShowRegisterModal(true);
    };

    const handleRegisterSuccess = () => {
        // After successful registration, user can sign in
        setStep("phone");
        setError("");
    };

    const handleBack = () => {
        if (step === "otp") {
            setStep("phone");
            setOtp("");
            setError("");
        } else {
            navigate("/");
        }
    };

    const handleCountryCodeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        // Only allow digits
        const value = e.target.value.replace(/\D/g, '');
        setCountryCode(value);
    };

    const handlePhoneNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        // Only allow digits
        const value = e.target.value.replace(/\D/g, '');
        setPhoneNumber(value);
    };

    if (isAuthLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'rgb(236, 229, 223)' }}>
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-button mx-auto mb-4"></div>
                    <p className="text-brand-body font-body">Loading...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: 'rgb(236, 229, 223)' }}>
            <div className="w-full max-w-md">
                {/* Header */}
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-heading text-brand-heading mb-4">
                        Welcome Back
                    </h1>
                    <p className="text-brand-body font-body">
                        {step === "phone"
                            ? "Sign in with your mobile number to continue your mindful journey"
                            : "Enter the verification code sent to your phone"
                        }
                    </p>
                </div>

                {/* Sign In Card */}
                <Card className="shadow-xl border-0">
                    <CardHeader className="text-center pb-4">
                        <div className="mx-auto mb-4 w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
                            {step === "phone" ? (
                                <Smartphone className="w-8 h-8 text-brand-button" />
                            ) : (
                                <MessageSquare className="w-8 h-8 text-brand-button" />
                            )}
                        </div>
                        <CardTitle className="text-2xl font-heading text-brand-heading">
                            {step === "phone" ? "Sign In" : "Verify Code"}
                        </CardTitle>
                        <CardDescription className="font-body text-brand-body">
                            {step === "phone"
                                ? "Enter your mobile number to receive a verification code"
                                : `We sent a 6-digit code to ${formatPhoneNumber()}`
                            }
                        </CardDescription>
                    </CardHeader>

                    <CardContent className="space-y-6">
                        {step === "phone" ? (
                            <form onSubmit={handlePhoneSubmit} className="space-y-4">
                                <div className="space-y-4">
                                    <div className="flex gap-3">
                                        <div className="flex-shrink-0 w-20">
                                            <Label htmlFor="countryCode" className="font-body text-brand-heading">
                                                Code
                                            </Label>
                                            <div className="relative">
                                                <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-brand-body font-body">+</span>
                                                <Input
                                                    id="countryCode"
                                                    type="text"
                                                    value={countryCode}
                                                    onChange={handleCountryCodeChange}
                                                    placeholder="1"
                                                    className="text-lg py-3 pl-7 pr-3 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body text-center"
                                                    disabled={isSubmitting}
                                                    maxLength={4}
                                                />
                                            </div>
                                        </div>
                                        <div className="flex-1">
                                            <Label htmlFor="phone" className="font-body text-brand-heading">
                                                Mobile Number
                                            </Label>
                                            <Input
                                                id="phone"
                                                type="text"
                                                value={phoneNumber}
                                                onChange={handlePhoneNumberChange}
                                                placeholder="5551234567"
                                                className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body"
                                                disabled={isSubmitting}
                                            />
                                        </div>
                                    </div>

                                    {(countryCode || phoneNumber) && (
                                        <div className="text-sm text-brand-body font-body">
                                            Your number: {formatPhoneNumber()}
                                        </div>
                                    )}
                                </div>

                                {error && (
                                    <p className="text-red-600 text-sm font-body">{error}</p>
                                )}

                                <Button
                                    type="submit"
                                    disabled={isSubmitting}
                                    className="w-full py-3 text-lg bg-brand-button hover:bg-brand-button/90 text-white font-body rounded-lg transition-all duration-300"
                                >
                                    {isSubmitting ? "Sending..." : "Send Verification Code"}
                                </Button>
                            </form>
                        ) : (
                            <form onSubmit={handleOtpSubmit} className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="otp" className="font-body text-brand-heading">
                                        Verification Code
                                    </Label>
                                    <Input
                                        id="otp"
                                        type="text"
                                        value={otp}
                                        onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                        placeholder="123456"
                                        className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body text-center tracking-widest"
                                        maxLength={6}
                                        disabled={isSubmitting}
                                    />
                                </div>

                                {error && (
                                    <p className="text-red-600 text-sm font-body">{error}</p>
                                )}

                                <Button
                                    type="submit"
                                    disabled={isSubmitting || otp.length !== 6}
                                    className="w-full py-3 text-lg bg-brand-button hover:bg-brand-button/90 text-white font-body rounded-lg transition-all duration-300"
                                >
                                    {isSubmitting ? "Verifying..." : "Verify & Sign In"}
                                </Button>
                            </form>
                        )}

                        {/* Register Section */}
                        <div className="pt-6 border-t border-gray-200">
                            <div className="text-center space-y-3">
                                <p className="text-sm text-brand-body font-body">
                                    Don't have an account?
                                </p>
                                <Button
                                    onClick={handleRegister}
                                    variant="outline"
                                    className="w-full border-2 border-brand-button text-brand-button hover:bg-brand-button hover:text-white transition-all duration-300 font-body"
                                >
                                    Register as New User
                                </Button>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Footer
                <div className="text-center mt-8">
                    <p className="text-sm text-gray-500 font-body">
                        By signing in, you agree to our Terms of Service and Privacy Policy
                    </p>
                </div> */}

                {/* Registration Modal */}
                <RegisterModal
                    isOpen={showRegisterModal}
                    onClose={() => setShowRegisterModal(false)}
                    onSuccess={handleRegisterSuccess}
                />
            </div>
        </div>
    );
};

export default SignIn; 