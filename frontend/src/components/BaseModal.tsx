
import { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

interface BaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  showCloseButton?: boolean;
  inline?: boolean;
  size?: 'default' | 'large' | 'xlarge';
}

const BaseModal = ({
  isOpen,
  onClose,
  title,
  children,
  showCloseButton = true,
  inline = false,
  size = 'default'
}: BaseModalProps) => {
  if (!isOpen) return null;

  if (inline) {
    return (
      <div className="mb-6 p-6 bg-orange-50 rounded-2xl border border-orange-200">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-brand-heading">{title}</h3>
          {showCloseButton && (
            <Button onClick={onClose} variant="ghost" size="sm" className="rounded-full">
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>
        {children}
      </div>
    );
  }

  const getModalSize = () => {
    switch (size) {
      case 'large':
        return 'max-w-4xl';
      case 'xlarge':
        return 'max-w-6xl';
      default:
        return 'max-w-2xl';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
      <div className={`bg-white rounded-2xl p-8 ${getModalSize()} w-full max-h-[90vh] overflow-y-auto animate-in zoom-in-95 duration-300 slide-in-from-bottom-4`}>
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-medium text-brand-heading">{title}</h2>
          {showCloseButton && (
            <Button onClick={onClose} variant="ghost" size="sm" className="rounded-full">
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>
        {children}
      </div>
    </div>
  );
};

export default BaseModal;
