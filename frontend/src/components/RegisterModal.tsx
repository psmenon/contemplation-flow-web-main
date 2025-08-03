import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { UserPlus } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

interface RegisterModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

const RegisterModal: React.FC<RegisterModalProps> = ({ isOpen, onClose, onSuccess }) => {
    const { register } = useAuth();
    const [countryCode, setCountryCode] = useState("1");
    const [phoneNumber, setPhoneNumber] = useState("");
    const [name, setName] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState(false);

    const formatPhoneNumber = () => {
        return `+${countryCode}-${phoneNumber}`;
    };

    const handleSubmit = async (e: React.FormEvent) => {
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

        if (!name.trim()) {
            setError("Please enter your name");
            return;
        }

        setIsLoading(true);

        try {
            const formattedPhoneNumber = formatPhoneNumber();
            const response = await register(formattedPhoneNumber, name);

            if (response.success) {
                setSuccess(true);
                setTimeout(() => {
                    onSuccess();
                    handleClose();
                }, 2000);
            }
        } catch (err: any) {
            setError(err.message || "Registration failed. Please try again.");
        } finally {
            setIsLoading(false);
        }
    };

    const handleClose = () => {
        setCountryCode("1");
        setPhoneNumber("");
        setName("");
        setError("");
        setSuccess(false);
        onClose();
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

    return (
        <Dialog open={isOpen} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <div className="mx-auto mb-4 w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
                        <UserPlus className="w-8 h-8 text-brand-button" />
                    </div>
                    <DialogTitle className="text-center text-2xl font-heading text-brand-heading">
                        Create Account
                    </DialogTitle>
                    <DialogDescription className="text-center font-body text-brand-body">
                        Join our mindful community by creating your account
                    </DialogDescription>
                </DialogHeader>

                {success ? (
                    <div className="py-6 text-center">
                        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <h3 className="text-lg font-heading text-brand-heading mb-2">Registration Successful!</h3>
                        <p className="text-brand-body font-body">
                            Your account has been created. You can now sign in with your phone number.
                        </p>
                    </div>
                ) : (
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="register-name" className="font-body text-brand-heading">
                                Full Name
                            </Label>
                            <Input
                                id="register-name"
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="John Doe"
                                className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body"
                                disabled={isLoading}
                            />
                        </div>

                        <div className="space-y-4">
                            <div className="flex gap-3">
                                <div className="flex-shrink-0 w-20">
                                    <Label htmlFor="register-countryCode" className="font-body text-brand-heading">
                                        Code
                                    </Label>
                                    <div className="relative">
                                        <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-brand-body font-body">+</span>
                                        <Input
                                            id="register-countryCode"
                                            type="text"
                                            value={countryCode}
                                            onChange={handleCountryCodeChange}
                                            placeholder="1"
                                            className="text-lg py-3 pl-7 pr-3 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body text-center"
                                            disabled={isLoading}
                                            maxLength={4}
                                        />
                                    </div>
                                </div>
                                <div className="flex-1">
                                    <Label htmlFor="register-phone" className="font-body text-brand-heading">
                                        Mobile Number
                                    </Label>
                                    <Input
                                        id="register-phone"
                                        type="text"
                                        value={phoneNumber}
                                        onChange={handlePhoneNumberChange}
                                        placeholder="5551234567"
                                        className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body"
                                        disabled={isLoading}
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

                        <div className="flex gap-3 pt-4">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleClose}
                                disabled={isLoading}
                                className="flex-1 border-2 border-gray-200 hover:bg-gray-50 font-body"
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={isLoading || !name.trim() || !countryCode.trim() || !phoneNumber.trim()}
                                className="flex-1 bg-brand-button hover:bg-brand-button/90 text-white font-body transition-all duration-300"
                            >
                                {isLoading ? "Creating..." : "Create Account"}
                            </Button>
                        </div>
                    </form>
                )}
            </DialogContent>
        </Dialog>
    );
};

export default RegisterModal; 